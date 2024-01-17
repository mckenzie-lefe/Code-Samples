import React, { Component } from 'react';
import { NotificationManager } from 'react-notifications';
import 'react-notifications/lib/notifications.css';
import './SignMessage.css';
import './SignDisplay.css';

export default class SignMessage extends Component {

    constructor(props) {
        super(props);
        this.state = {
            controlPanels: [],
            selectedPanels: new Set(),
            displayType: "",
            duration: "5 mins",
            text: "",
            isLoading: false,
            notification: ""
        };
        
        this.checkApplyParameters = this.checkApplyParameters.bind(this);
        this.handleDurationChange = this.handleDurationChange.bind(this);
        this.handleTextChange = this.handleTextChange.bind(this);
        this.handleApplyBtnClicked = this.handleApplyBtnClicked.bind(this);
        this.handleMsgTypeChange = this.handleMsgTypeChange.bind(this);
        this.handleSelectedPanelsChange = this.handleSelectedPanelsChange.bind(this);
    }

    componentDidMount() {
        this.setState({ controlPanels: this.props.controlPanels });
    }

    toggleLoading = () => {
        this.setState((prevState) => ({
            isLoading: !prevState.isLoading
        }))
    }

    async handleApplyBtnClicked() {
        if (this.checkApplyParameters()) {
            console.log("SM@ Handling apply button clicked ...");
            this.toggleLoading()
  
            const response = await fetch('/apply', {
                method: 'POST',
                body: JSON.stringify({
                    controlPanels: Array.from(this.state.selectedPanels),
                    displayType: this.state.displayType,
                    duration: this.state.duration,
                    text: this.state.text,
                }),
                headers: {
                    'Content-type': 'application/json; charset=UTF-8',
                }
            });
            const data = await response.json();
            this.toggleLoading();
            console.log('SM@ Response: ' + JSON.stringify(data));

            for (let i in data) {
                this.createNotification(data[i].panelName, data[i].status);
            }
        }
        else {
            // TO DO: handle missing parameters
            console.log("missing parameters" );
        } 
    }

    createNotification(des, type) {
        console.log("SM@ create notification ...");
        switch (type) {
            case "ALERT":
                NotificationManager.warning("Cannot change " + des + " display when alert is playing.", "Custom Message denied. ", 8000);
                break;
            case "SERVER-BUSY":
                NotificationManager.warning("Annunciator busy processing different request. Try again later.", des + "Busy", 6000);
                break;
            case "SIGN-BUSY":
                NotificationManager.warning("Sign is busy processing other commands. Try again later.", des + "Busy", 6000);
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
            case "EXC", "BAD-REQ":
                NotificationManager.error("An unknown error occured.", "FAIL", 6000);
                break;
        }
    }

    checkApplyParameters() {
        // returns false if not all parameters have values
        let applyOk = true;

        if (this.state.displayType === "") {
            NotificationManager.warning("Select before pushing apply.", "Missing Display Type", 4000);
            applyOk = false;
        }
           
        if (this.state.selectedPanels.size === 0) {
            NotificationManager.warning("Select before pushing apply.", "Missing Panels Selection", 4000);
            applyOk = false;
        }
            
        return applyOk;
    }

    handleTextChange(event) {
        this.setState({ text: event.target.value });
    }

    handleDurationChange(event) {
        this.setState({ duration: event.target.value })
    }

    handleMsgTypeChange(event) {
        this.setState({ displayType: event.target.value })
    }

    handleSelectedPanelsChange(event) {
        if (event.target.checked) { // add panel
            this.setState(({ selectedPanels }) => ({ selectedPanels: new Set(selectedPanels).add(event.target.value) }));
        }
        else { // remove panel
            this.setState(({ selectedPanels }) => {
                const newSelected = new Set(selectedPanels);
                newSelected.delete(event.target.value);

                return { selectedPanels: newSelected };
            });
        }
    }

    render() {
        return (
            <div className="sign-message">
                <b id="title">Custom Message</b>
                <textarea className="text-input" type="text" name="messageText" onChange={this.handleTextChange} value={this.state.text}/>
                <select className="durations" id="durations" onChange={this.handleDurationChange}>
                    <option value="5m">5 minutes</option>
                    <option value="10m">10 minutes</option>
                    <option value="30m">30 minutes</option>
                </select>
                <div className="control-panels" onChange={this.handleSelectedPanelsChange}>
                    <div className="panel-options">
                        {this.state.controlPanels.map((panel) => {
                            let key = panel + "-cb"
                            return (
                                <div key={key}>
                                    <input type="checkbox" id={panel} className="panel-checkbox" value={panel}></input>
                                    <label htmlFor={panel}>{panel}</label>
                                </div>
                            )
                        })}
                    </div>
                </div>
                <div className="message-type" onChange={this.handleMsgTypeChange}>
                    <input type="radio" id="dangerMsg" name="msgType" value="danger"></input>
                    <label htmlFor="dangerMsg">Danger</label>
                    <input type="radio" id="warningMsg" name="msgType" value="warning"></input>
                    <label htmlFor="warningMsg">Warning</label>
                    <input type="radio" id="infoMsg" name="msgType" value="info"></input>
                    <label htmlFor="infoMsg">Info</label>
                </div>
                {!this.state.isLoading && <button className="apply-btn" onClick={this.handleApplyBtnClicked}>APPLY</button>}
                {this.state.isLoading && <button className="apply-btn">APPLYING...</button>}
                <br></br>
            </div>      
        );
    }
}
