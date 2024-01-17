using Microsoft.AspNetCore.Mvc;
using System.Net;
using System.Net.Sockets;
using Microsoft.Extensions.FileProviders;
using System.IO;
using Microsoft.VisualBasic;
using System.Text;
using static System.Net.Mime.MediaTypeNames;
using System.Reflection.Metadata;
using System.Globalization;
using System.Collections.Generic;
using backend;

// For more information on enabling Web API for empty projects, visit https://go.microsoft.com/fwlink/?LinkID=397860
//https://stackoverflow.com/questions/71856877/receiveasyncs-cancellationtoken-paramtere-is-doing-timeout-even-if-the-web-sock
namespace webapi.Controllers
{
    [ApiController]
    [Route("")]
    public class SignController : ControllerBase
    {
        Dictionary<string, (string, int)> panels = 
            new Dictionary<string, (string, int)>();
        
        private readonly ILogger<SignController> _logger;    
        private string client_code = "A";

        public SignController(ILogger<SignController> logger)
        {
            _logger = logger;
            panels.Add("Office", ("XXIPXX", 1234));
            panels.Add("33-PNL-701", ("XXIPXX", 1234));
            panels.Add("33-PNL-702", ("XXIPXX", 1234));
        }

        /* Used to check if site is online
         * URL: http://XXXX:XXXX/ 
         */
        [HttpGet]
        public IActionResult Get()
        {
            return Ok("Site working");
        }

        /* Get panel names
         * URL: http://XXXX:XXXX/panels 
         */
        [HttpGet("panels")]
        public IActionResult GetPanels()
        {
            List<string> panelNames = new List<string>();
            Console.WriteLine($"GET-PANELS: enter");
            try
            {
                if (!ModelState.IsValid)
                    return Ok("bad request");

                foreach (var panel in panels)
                {
                    panelNames.Add(panel.Key);
                }

                Console.WriteLine("GET-PANELS: exit");
                return Ok(panelNames);
            }
            catch (Exception exc)
            {
                _logger.LogInformation("exc - {Exception}", exc);
                var exc_ = "exc - " + exc;
                Console.WriteLine("GET-PANELS: exit2");
                return Ok(exc_.ToString());
            }
        }

        /************************************************************************/

        /* Change sign display to drums
         * URL: http://XXXX:XXXX/setdrums/{$PANEL_NAME}
         */
        [HttpGet]
        [Route("setdrums/{panel}")]
        public IActionResult SetDrums(string panel)
        {
            Console.WriteLine($"SET-DRUMS: {panel}");
            try
            {
                if (!ModelState.IsValid)
                    return Ok(new Result {panelName = panel, status = "BAD-REQ"});

                var result = RequestDrumsDisplay(panel).Result;
                
                Console.WriteLine("SET-DRUMS: exit");
                return Ok(result);
            }
            catch (Exception exc)
            {
                _logger.LogInformation("exc - {Exception}", exc);
                Console.WriteLine("SET-DRUMS: exc:" + exc);
                return Ok(new Result { panelName = panel, status = "ERROR" });
            }
        }

        /* SetDrums Helper, Socket communication with AnnunciatorServer
         * 
         */
        private async Task<Result> RequestDrumsDisplay(string panel)
        {
            string status = "COMMS-ERROR";
            string resp; 
            var (ip, port) = panels[panel];
            byte[] sendBytes;
            byte[] buffer;
            int received;
            var timeOut = new CancellationTokenSource(5000).Token;
            IPEndPoint ipEndPoint = new(IPAddress.Parse(ip), port);
            Socket client = new(ipEndPoint.AddressFamily, SocketType.Stream, ProtocolType.Tcp);

            try
            {
                await client.ConnectAsync(ipEndPoint, timeOut);
                if (client.Connected)
                {
                    try
                    {
                        // Send A2 => webserver requesting drums display
                        sendBytes = Encoding.UTF8.GetBytes(client_code + "2");
                        var bytes_sent = await client.SendAsync(sendBytes, SocketFlags.None, timeOut);
                        Console.WriteLine("DIS-sent: " + bytes_sent.ToString() + " - " + panel);

                        // Receive result
                        buffer = new byte[1_024];
                        received = await client.ReceiveAsync(buffer, SocketFlags.None);
                        resp = Encoding.UTF8.GetString(buffer, 0, received);
                        Console.WriteLine($"DIS-Code Recevied: {resp} = {panel}");

                        if (resp.Equals("ACK"))
                        {
                            Console.WriteLine($"DIS-{panel} successful");
                            status = "SUCC";
                        }
                        else if (resp.Equals("NAK"))
                        {
                            Console.WriteLine($"DIS-{panel} Failed to update sign with message");
                            status = "FAIL";
                        }
                        else if (resp.Equals("BUSY"))
                        {
                            Console.WriteLine($"DIS-{panel} Sign busy processing other request");
                            status = "SIGN-BUSY";
                        }
                        else if (resp.Equals("POWERCYCLE"))
                        {
                            Console.WriteLine($"DIS-{panel} Sign is power cycling");
                            status = "POWER-CYCLE";
                        }
                        else
                        {
                            Console.WriteLine($"DIS-{panel} Error command not acknowledged.");
                            status = "INVALID-CMD";
                        }

                    } catch (Exception e) {
                        Console.WriteLine($"DIS-{panel} Communication error in SetDrums: {e}");
                    }
                }
                client.Shutdown(SocketShutdown.Both);
                return new Result { panelName = panel, status = status };
            }
            catch (Exception e)
            {
                Console.WriteLine($"DIS-{panel} Error in SetDrums: {e}");
                return new Result { panelName = panel, status = "ERROR" };
            }
        }

        /************************************************************************/

        /* Get current sign displays 
         * URL:  http://XXXX:XXXX/signdisplays 
         * 
         */
        [HttpGet("signdisplays")]
        public IActionResult GetSignDisplays()
        {
            try
            {
                if (!ModelState.IsValid)
                    return Ok("GET-bad request");

                var result = RequestCurrentDisplay().Result;
                return Ok(result);
            }
            catch (Exception exc)
            {
                _logger.LogInformation("exc - {Exception}", exc);
                Console.WriteLine("GET-exc:"+ exc);
                return Ok(new SignDisplay[] { new SignDisplay {
                    panelName = "ERROR",
                    displayType =  "unknown",
                }});
            }
        }

        /* Helper for RequestCurrentDisplay
         * Creates SignDisplay object from received data
         */
        private SignDisplay CreateSignDisplay(string panel, string code,
            string content)
        {
            List<DrumState> drum_states = new List<DrumState>();

            if (code.Equals("0"))
            {
                Console.WriteLine(content);
                var drums = content.Split('_');
                foreach (var drum in drums)
                {
                    var state_info = drum.Split(',');
                    if (state_info.Length > 1)
                    {
                        var dur = state_info[2].Split(':');

                        drum_states.Add(new DrumState
                        {
                            state = TimerCodeToString(state_info[0]),
                            timerStart = state_info[1],
                            timerDuration = new TimeSpan(0, Int32.Parse(state_info[2]), 0),
                            timerDetails = state_info[3]
                        });
                    }
                    else
                    {
                        drum_states.Add(new DrumState { state = StageCodeToString(state_info[0]) });
                    }
                }

                /*var stages = new List<string> {
                    StageCodeToString(content.Substring(0, 1)),
                    StageCodeToString(content.Substring(1, 1)),
                    StageCodeToString(content.Substring(2, 1)),
                    StageCodeToString(content.Substring(3, 1)),
                    StageCodeToString(content.Substring(4, 1)),
                    StageCodeToString(content.Substring(5, 1))
                };*/

                /*if (timer_content.Contains("NO-TIMER")) // no timer set
                {
                    return new SignDisplay
                    {
                        panelName = panel,
                        displayType = DisplayCodeToString(code),
                        stages = stages
                    };
                }*/

                return new SignDisplay
                {
                    panelName = panel,
                    displayType = DisplayCodeToString(code),
                    states = drum_states
                };
            }

            return new SignDisplay
            {
                panelName = panel,
                displayType = DisplayCodeToString(code),
                message = content
            };
        }

        /* Helper for RequestCurrentDisplay
         * 
         * Display Type Codes: 0=drums, 1=danger, 2=warning, 3=info,
         *                     4=notification, 5=alert
         */
        private string DisplayCodeToString(string code)
        {
            if (code.Equals("0")) return "drums";
            else if (code.Equals("1")) return "danger";
            else if (code.Equals("2")) return "warning";
            else if (code.Equals("3")) return "info";
            else if (code.Equals("4")) return "notify";
            else if (code.Equals("5")) return "alert";
            else if (code.Equals("6")) return "notify";  // treat error as notify
            else return "unknown";
        }

        /* Helper for RequestCurrentDisplay
         * NOTE: Should never be 0
         * Timer Codes: 0=no timer, 1=iso valve
         */
        private string TimerCodeToString(string code)
        {
            if (code.Equals("0")) return "none";
            else if (code.Equals("1")) return "isotimer";
            //  #### Add more timers here ####
            else return "unset";

        }

        /* Helper for RequestCurrentDisplay
         * 
         * Stage Codes: 0=online, 1=switch, 2=steam, 3=quench, 4=vent, 
         *       5=drain, 6=cut, 7=o2free, 8=pressTest, 9=prewarm
         *       10=isotimer
         */
        private string StageCodeToString(string code)
        {
            if (code.Equals("0")) return "online";
            else if (code.Equals("1")) return "switch";
            else if (code.Equals("2")) return "steam";
            else if (code.Equals("3")) return "quench";
            else if (code.Equals("4")) return "vent";
            else if (code.Equals("5")) return "drain";
            else if (code.Equals("6")) return "cut";
            else if (code.Equals("7")) return "o2free";
            else if (code.Equals("8")) return "presstest";
            else if (code.Equals("9")) return "prewarm";
            else return "unset";
        }

        private async Task<SignDisplay[]> RequestCurrentDisplay()
        {
            var results = new List<Task<SignDisplay>>();

            try {
                foreach (var panel in panels)
                {
                    results.Add(RequestCurrentDisplay(panel.Key));
                }
            }
            catch (Exception e)
            {
                Console.WriteLine("GET-exc catch: " + e);
            }
            return await Task.WhenAll(results);
        }

        /*
         * 
         * Return displayCode is -1 if exc occured, -2 if ACK not recieved. 
         */
        private async Task<SignDisplay> RequestCurrentDisplay(string panel)
        {
            string content = "";
            string code = "";
            var (ip, port) = panels[panel];
            byte[] sendBytes;
            byte[] buffer = new byte[1_024];
            int received;
            var timeOut = new CancellationTokenSource(5000).Token;
            IPEndPoint ipEndPoint = new(IPAddress.Parse(ip), port);
            Socket client = new(ipEndPoint.AddressFamily, SocketType.Stream, ProtocolType.Tcp);

            try
            {
                await client.ConnectAsync(ipEndPoint, timeOut);
                if (client.Connected)
                {
                    // Send A3 => webserver requesting current display
                    sendBytes = Encoding.UTF8.GetBytes(client_code + "3");
                    var bytes_sent = await client.SendAsync(sendBytes, SocketFlags.None, timeOut);
                
                    try // Receive display code and content
                    {
                        //buffer = new byte[1_024];
                        received = await client.ReceiveAsync(buffer, SocketFlags.None, timeOut);
                        code = Encoding.UTF8.GetString(buffer, 0, received);

                        //buffer = new byte[1_024];
                        received = await client.ReceiveAsync(buffer, SocketFlags.None, timeOut);
                        content = Encoding.UTF8.GetString(buffer, 0, received);

                    }
                    catch (Exception e)
                    {
                        Console.WriteLine($"REQ-{panel} Error receiving display code: {e}");
                        code = "-1";
                    }
                }
                client.Shutdown(SocketShutdown.Both);
            }
            catch (Exception e)
            {
                Console.WriteLine($"REQ-{panel} Error in SendMessage: {e}");
                code = "-1";
            }

            return CreateSignDisplay(panel, code, content);
        }

        /************************************************************************/

        /* url: http://XXXX:XXXX/apply 
         * Called by reactapp when apply button is clicked. The
         * json string created by the reactapp macthes the format of 
         * SignMessgae.
         * 
         * - If no message in body of request BadRequest returned. 
         * - If execption occurred in the processing of the message 
         *  the expection will be returned in body of response. 
         * - If message was successfull applied to the given signs,  
         *  the message is returned in the response.
        */
        [HttpPost]
        [Route("apply")]
        public IActionResult ApplyMessage([FromBody] SignMessage signMsg)
        {
            Console.WriteLine($"APPLY-MESSAGE");
            try
            {
                if (signMsg == null || !ModelState.IsValid)
                    return Ok(new Result { panelName = "", status = "BAD-REQ" }); 

                var result = SendMessage(signMsg).Result;
                foreach ( var r in result)
                {
                    Console.WriteLine(r);
                }
                Console.WriteLine("APPLY-exit");
                return Ok(result);
            }
            catch (Exception exc)
            {
                _logger.LogInformation("APPLY-exc - {Exception}", exc);
                return Ok(new Result { panelName = "", status = "EXC" });
            }
        }

        private async Task<Result[]> SendMessage(SignMessage signMsg)
        {
            var results = new List<Task<Result>>();
            var msg = CreateMessageString(signMsg.displayType, signMsg.duration, signMsg.text);

            foreach (var panel in signMsg.controlPanels)
            {
                results.Add(SendMessage(panel, msg));
            }
            return await Task.WhenAll(results);
        }

        private async Task<Result> SendMessage(string panel, string msg)
        {
            string status = "COMMS-ERROR";
            byte[] sendBytes;
            byte[] buffer;
            int received;
            string resp;
            var (ip, port) = panels[panel];
            var timeOut = new CancellationTokenSource(5000).Token; 
            var receiveTimeOut = new CancellationTokenSource(25000).Token;
            IPEndPoint ipEndPoint = new(IPAddress.Parse(ip), port);
            Socket client = new(ipEndPoint.AddressFamily, SocketType.Stream, ProtocolType.Tcp);

            try
            {
                await client.ConnectAsync(ipEndPoint, timeOut); 
                if (client.Connected) 
                {
                    try
                    {
                        // Send A1 => webserver requesting custom message display
                        sendBytes = Encoding.UTF8.GetBytes(client_code + "1");
                        var bytes_sent = await client.SendAsync(sendBytes, SocketFlags.None, timeOut);
                        Console.WriteLine($"APPLY-{panel} sent: " + bytes_sent.ToString());

                        // Receive ack.
                        buffer = new byte[1_024];
                        received = await client.ReceiveAsync(buffer, SocketFlags.None, timeOut);
                        resp = Encoding.UTF8.GetString(buffer, 0, received);
                        Console.WriteLine($"APPLY-{panel} recev: {resp}");

                        if (resp.Equals("ACK"))
                        {
                            // Send message length 
                            var msgLen = msg.Length.ToString();
                            sendBytes = Encoding.UTF8.GetBytes(msgLen);
                            _ = await client.SendAsync(sendBytes, SocketFlags.None, timeOut);
                            Console.WriteLine($"APPLY-{panel} sent: {msgLen}");

                            // Send message 
                            sendBytes = Encoding.UTF8.GetBytes(msg);
                            _ = await client.SendAsync(sendBytes, SocketFlags.None, timeOut);
                            Console.WriteLine($"APPLY-{panel} sent: {msg}");

                            // Receive ack.
                            buffer = new byte[1_024];
                            received = await client.ReceiveAsync(buffer, SocketFlags.None, receiveTimeOut);
                            resp = Encoding.UTF8.GetString(buffer, 0, received);
                            Console.WriteLine($"APPLY-{panel} Recevied: {resp}");

                            if (resp.Equals("BUSY"))
                            {
                                Console.WriteLine($"APPLY-{panel} Error applying custom message sign is BUSY."); 
                                status = "SIGN-BUSY";
                            }
                            else if (resp.Equals("ALERT"))
                            {
                                Console.WriteLine($"APPLY-{panel} FAIL, alert playing.");
                                status = "ALERT";
                            }
                            else if (resp.Equals("ACK"))
                            {
                                Console.WriteLine($"APPLY-{panel} SUCCESSFUL");
                                status = "SUCC";
                            }
                            else if (resp.Equals("NAK"))
                            {
                                Console.WriteLine($"APPLY-{panel} Failed to update sign with message");
                                status = "FAIL";
                            }
                            else
                            {
                                Console.WriteLine($"APPLY-{panel} last resp not recongized");
                                status = "FAIL";
                            }
                        }
                        else if (resp.Equals("BUSY"))
                        {
                            Console.WriteLine($"APPLY-{panel} Sign busy processing other custom message request");
                            status = "SERVER-BUSY";
                        }
                        else if (resp.Equals("POWERCYCLE"))
                        {
                            Console.WriteLine($"APPLY-{panel} Sign is power cycling");
                            status = "POWER-CYCLE";
                        }
                        else
                        {
                            Console.WriteLine($"APPLY-{panel} Error command not acknowledged. name");
                            status = "INVALID-CMD";
                        }
                    
                    } catch (Exception e){
                        Console.WriteLine($"APPLY-{panel} Communication Error - {e}");
                    }
                }

                client.Shutdown(SocketShutdown.Both);
                return new Result { panelName = panel, status = status };
            }
            catch (Exception e)
            {
                Console.WriteLine($"APPLY-{panel} Error in SendMessage: {e}");
                return new Result { panelName = panel, status = "ERROR" };
            }
        }

        /* Helper for SendMessage 
         * Display Type Codes: 0=drums, 1=danger, 2=warning, 3=info,
         *                     4=notification, 5=alert 
         *      
         * Duration Codes: 0=5m, 1=10m, 2=30m
         */
        private string CreateMessageString(string displayType, string duration, 
            string text)
        {
            string msg = "";

            if (displayType.Equals("danger"))
                msg = msg + "1";
            else if (displayType.Equals("warning"))
                msg = msg + "2";
            else if (displayType.Equals("info"))
                msg = msg + "3";
            else
                Console.WriteLine($"Invalid displayType: {displayType}");

            if (duration.Equals("10m"))
                msg = msg + "1";
            else if (duration.Equals("30m"))
                msg = msg + "2";
            else    // defualt 5 mins
                msg = msg + "0";

            return msg + text;
        }

    }
}
