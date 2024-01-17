import React, { Component } from 'react';
import { NotificationManager } from 'react-notifications';
import DrumState from "./DrumState.js";
import './SignDisplay.css'


export default class SignDisplay extends Component {

    constructor(props) {
        super(props);
        this.state = {
            displayType: "",
            displayContent: "",
            message: [""],
            errorCounter: 0,
            isLoading: false
        };
        this.max_errors = 5
        this.pageIndex = 0;
        this.update = this.update.bind(this);
        this.setDrums = this.setDrums.bind(this);
        this.changeMessagePage = this.changeMessagePage.bind(this);
        this.drums = [ React.createRef(), React.createRef(), React.createRef(),
                        React.createRef(), React.createRef(), React.createRef() ];
    }

    componentWillUnmount() {
        clearInterval(this.timerID);
    }

    toggleLoading = () => {
        this.setState((prevState) => ({
            isLoading: !prevState.isLoading
        }))
    }

    // NO LONGER USED
    async updateOld(signDisplay) {
        const messageDisplays = ["info", "warning", "danger", "notify", "alert"];

        if (signDisplay.displayType === "drums") {

            if (this.state.displayType === "drums") {
                // check if state.stages needs to be updated
                let stages_unchanged = true;
                for (let i in this.state.stages) {
                    if (this.state.stages[i] !== signDisplay.stages[i]) {
                        stages_unchanged = false;
                        break;
                    }
                }
                if (stages_unchanged)
                    return;
            }
            // update state if displayType or stages have changed
            console.log('Update drums - ' + signDisplay.panelName)
            this.setState({
                displayType: signDisplay.displayType,
                stages: signDisplay.stages,
                errorCounter: 0
            })

        } else if (messageDisplays.includes(signDisplay.displayType)) {
            let pages = this.handleLongMessage(signDisplay.message, signDisplay.displayType);
            // type different or type the same but different message
            if ((this.state.displayType !== signDisplay.displayType) ||
                (this.state.displayType === signDisplay.displayType &&
                    JSON.stringify(this.state.message) !== JSON.stringify(pages))) {

                console.log('Update msg - ' + signDisplay.panelName)
                this.setState({
                    displayType: signDisplay.displayType,
                    displayContent: pages[0],
                    message: pages,
                    errorCounter: 0
                })

                if (pages.length > 1)
                    this.startMessageFlipTimer();
            }

        } else {    // unknown
            if (this.state.displayType !== "unknown" &&
                this.state.errorCounter >= this.max_errors) {
                console.log('Update unknown - ' + signDisplay.panelName)
                this.setState({ displayType: signDisplay.displayType });
            }

            this.setState(prevState => {
                return { errorCounter: prevState.errorCounter + 1 }
            });
        }
    }

    updateStates(states) {
        for (let i in this.drums) {
            if (this.drums[i].current.state.drumState !== states[i].state) {
                this.drums[i].current.update(states[i])
            }
        }
    }

    /**
     * @param {object} signDisplay
     * @param {string} signDispla.panelName equiv. to props.name 
     * @param {string} signDispla.displayType one of 
     *      ["drums", "unknown", "info", "alert", "warning", "danger", "notify"]
     * @param {string} signDisplay.message text with 999 characters or less. Only set if
     *                  displayType in messageDisplays
     * @param {Array<string>} signDisplay.stages items in ["online", switch", "steam", 
     *      "quench", "vent", "drain", "cut", "o2free", "presstest", "prewarm", "unset"]
     */
    async update(signDisplay) {    
        const messageDisplays = ["info", "warning", "danger", "notify", "alert"];

        if (signDisplay.displayType === "drums") {

            if (this.state.displayType !== "drums") {
                // set drums & update state 
                console.log('Set drums - ' + signDisplay.panelName)
                this.setState({
                    displayType: signDisplay.displayType,
                    errorCounter: 0
                }, () => { this.updateStates(signDisplay.states); });

            } else {
                //console.log('Update state - ' + signDisplay.panelName)
                this.updateStates(signDisplay.states);
            }

        } else if (messageDisplays.includes(signDisplay.displayType)) {
            let pages = this.handleLongMessage(signDisplay.message, signDisplay.displayType);
            // type different or type the same but different message
            if ((this.state.displayType !== signDisplay.displayType) ||
                (this.state.displayType === signDisplay.displayType &&
                JSON.stringify(this.state.message) !== JSON.stringify(pages))) {

                console.log('Update msg - ' + signDisplay.panelName)
                this.setState({
                    displayType: signDisplay.displayType,
                    displayContent: pages[0],
                    message: pages,
                    errorCounter: 0
                })

                if (pages.length > 1) 
                    this.startMessageFlipTimer();
            }

        } else {    // unknown
            if (this.state.displayType !== "unknown" &&
                this.state.errorCounter >= this.max_errors) {
                console.log('Update unknown - ' + signDisplay.panelName)
                this.setState({ displayType: signDisplay.displayType });
            }

            this.setState(prevState => {
                return { errorCounter: prevState.errorCounter + 1 }
            });
        }
    }

    async setDrums(panel) {
        console.log(panel);
        this.toggleLoading();
        const response = await fetch('/setdrums/' + panel);
        const data = await response.json();
        console.log("HI");
        console.log(JSON.stringify(data));
        this.toggleLoading();
        this.createNotification(data.panelName, data.status);
    }

    createNotification(des, type) {
        console.log("SD create notification ...");
        switch (type) {
            case "SUCC":
                break;
            case "ALERT":
                NotificationManager.warning("Cannot revert " + des + " to drums when alert is playing.", "Revert to drums denied. ", 8000);
                break;
            case "SIGN-BUSY":
                NotificationManager.warning("Sign is busy processing other commands. Try again later.", des + " Busy", 6000);
                break;
            case "POWER-CYCLE":
                NotificationManager.warning("Wait a couple minutes and try again.", des + " Power Cycling", 6000);
                break;
            case "COMMS-ERROR":
                NotificationManager.error("Error communicating with control panel.", des + " Apply Failed", 6000);
                break;
            case "ERROR":
                NotificationManager.error("An unknown error occured.", des + " Apply Failed", 6000);
                break;
            default:
                NotificationManager.error("An unknown error occured.", des + " FAIL", 6000);
                break;
        }
    }

    /**
     * Handles messages that are too long to fit on sign display by 
     * seperating text into pages. This pages will alternate on the sign
     * display on a timer until display is changed.
     * 
     * Each page has two lines, each line has a char. max of 34.
     * Does not allow word breaks between lines.
     * 
     * @param {string} msg text to break apart
     * @param {string} msgType
     * @returns An array of strings, each containing a pages text.
     */
    handleLongMessage(msg, msgType) {
        let words = msg.split(" ");
        let pages = [];
        let pageCount = 0;
        let lineCount = 0;
        let l1 = true;
        
        // count space for message label
        if (msgType === 'warning')
            lineCount = 12;
        else if (msgType === 'danger')
            lineCount = 11;

        pages[pageCount] = ""
        for (let i in words) {
            // check if end of line
            if (lineCount + words[i].length >= 37) { 
                if (!l1) {      // start new page at end of second line
                    pageCount = pageCount + 1;
                    pages[pageCount] = "";
                }
                lineCount = 0;
                l1 = !l1;
            }
            pages[pageCount] = pages[pageCount] + words[i] + " ";
            lineCount = lineCount + words[i].length + 1;
        }
        return pages;
    }

    startMessageFlipTimer() {
        // flip every 7 seconds 
        this.timerID = setInterval(() => this.changeMessagePage(), 7000 );
    }

    stopMessageFlipTimer() {
        clearInterval(this.timerID)
    }

    changeMessagePage() {
        this.pageIndex = (this.pageIndex + 1) % this.state.message.length;
        this.setState({ displayContent: this.state.message[this.pageIndex] });
    }

    getDrumStage(drumStage) {
        if (drumStage === "online") {
            return (<small id="online">online</small>);
        }
        else if (drumStage === "switch") {
            return (<small id="switch">switch</small>);
        }
        else if (drumStage === "steam") {
            return (<small id="steam">steam</small>);
        }
        else if (drumStage === "quench") {
            return (<small id="quench">quench</small>);
        }
        else if (drumStage === "vent") {
            return (<small id="vent">vent</small>);
        }
        else if (drumStage === "drain") {
            return (<small id="drain">drain</small>);
        }
        else if (drumStage === "cut") {
            return (<small id="cut">cut</small>);
        }
        else if (drumStage === "o2free") {
            return (<small id="o2free">O2 Free</small>);
        }
        else if (drumStage === "presstest") {
            return (<small id="presstest">press test</small>);
        }
        else if (drumStage === "prewarm") {
            return (<small id="prewarm">prewarm</small>);
        }
        else if (drumStage === "isotimer") {
            return (<small id="isotimer">Close HVXX</small>);
        }
        else {
            return (<small id="unset">----</small>);
        }
    }   
    
    drumsDisplay() {
        return (
            <div className="drums-display">
                <DrumState key="D1A" name="D1A" ref={this.drums[0]} />
                <DrumState key="D2A" name="D2A" ref={this.drums[2]} />
                <DrumState key="D3A" name="D3A" ref={this.drums[4]} />
                <DrumState key="D1B" name="D1B" ref={this.drums[1]} />
                <DrumState key="D2B" name="D2B" ref={this.drums[3]} />
                <DrumState key="D3B" name="D3B" ref={this.drums[5]} />
            </div>
        )
    }

    drumsDisplayOLD() {
        return (
            <div className="drums-display">
                <div className="drum-status">
                    <span id="drum-labelA">1A</span>
                    {this.getDrumStage(this.state.stages[0])}
                </div>
                <div className="drum-status">
                    <span id="drum-labelA">2A</span>
                    {this.getDrumStage(this.state.stages[2])}
                </div>
                <div className="drum-status">
                    <span id="drum-labelA">3A</span>
                    {this.getDrumStage(this.state.stages[4])}
                </div>
                <div className="drum-status">
                    <span id="drum-labelB">1B</span>
                    {this.getDrumStage(this.state.stages[1])}
                </div>
                <div className="drum-status">
                    <span id="drum-labelB">2B</span>
                    {this.getDrumStage(this.state.stages[3])}
                </div>
                <div className="drum-status">
                    <span id="drum-labelB">3B</span>
                    {this.getDrumStage(this.state.stages[5])}
                </div>
            </div>
        )
    }

    infoDisplay() {
        return (
            <div className="info-display">
                <b>{this.state.displayContent}</b>
            </div>
        )
    }

    dangerDisplay() {
        return (
            <div className="danger-display">
                {(this.pageIndex === 0) && <span className="msg-label">Danger: </span>}<b className="msg-content">{this.state.displayContent}</b>            
            </div>
        )
    }

    warningDisplay() {
        return (
            <div className="warning-display">
                {(this.pageIndex === 0) && <span className="msg-label">Warning: </span>}  
                <b className="msg-content">{this.state.displayContent}</b>              
            </div>
        )
    }

    notifyDisplay() {
        return (
            <div className="notify-display">
                <span className="msg-content">{this.state.displayContent}</span>
            </div>
        )
    }

    alertDisplay() {
        // displayContent format: '<alarms> detected on <decks> '
        let alertText = this.state.displayContent.split("detected on");
        return (
            <div className="alert-display">
                <b id="alarms">{alertText[0]}</b>
                <b>DETECTED ON</b>
                <br></br>
                <b>{alertText[1]}</b>
            </div>
        )
    }

    render() {
        let display, show_drums;
        if (this.state.displayType === 'drums') {
            show_drums = true;
            display = this.drumsDisplay();
        }
        else if (this.state.displayType === 'danger') {
            display = this.dangerDisplay();
        }
        else if (this.state.displayType === 'warning') {
            display = this.warningDisplay();
        }
        else if (this.state.displayType === 'info') {
            display = this.infoDisplay();
        }
        else if (this.state.displayType === 'alert') {
            display = this.alertDisplay();
        }
        else if (this.state.displayType === 'notify') {
            display = this.notifyDisplay();
        }
        else {
            display = <div className="unknown-display">Display unknown.</div>;
        }

        return (
            <div className="sign">
                <div className="display-bar">
                    <b className="sign-label">{this.props.name}</b>
                    {!this.state.isLoading &&
                        <button className="drums-btn" onClick={() => this.setDrums(this.props.name)}>REVERT TO DRUMS</button>}
                    {this.state.isLoading &&
                        <button className="drums-btn" onClick={() => this.setDrums(this.props.name)}>REVERTING...</button>}
                </div>
                <div className="display">
                    {display}
                </div>
            </div>
        )
    }
}
