import React, { Component } from 'react';
import { NotificationContainer } from 'react-notifications';
import SignMessage from "./SignMessage.js";
import SignDisplay from "./SignDisplay.js";
import './MainPage.css';

/*
 * Error handling await functions: https://catchjs.com/Docs/AsyncAwait
 */

export default class MainPage extends Component {

    constructor(props) {
        super(props);
        this.state = {
            controlPanels: null,
        };

        this.populateControlPanels = this.populateControlPanels.bind(this);
        this.refreshSignDisplays = this.refreshSignDisplays.bind(this);
        this.intervalUpdate = this.intervalUpdate.bind(this);
    }

    componentDidMount() {
        this.populateControlPanels().catch();
        this.refreshSignDisplays().catch();            
        this.interval = setInterval(this.intervalUpdate, 3000);
    }

    componentWillUnmount() {
        clearInterval(this.interval);
    }
 
    async populateControlPanels() {
        console.log("MP@ Getting panels...");
        const response = await fetch('/panels');
        const data = await response.json();
        this.setState({ controlPanels: data });
        for (let i in data) {
            this[data[i] + "SignDisplay"] = React.createRef();
        }
    }

    async refreshSignDisplays() {
        const response = await fetch('/signdisplays');
        const data = await response.json();

        for (let i in data) {
            if (data[i].panelName === "ERROR") {
                console.log('ERROR fetching displays');
                continue;
            }

            try {
                this[data[i].panelName + "SignDisplay"].current.update(data[i]);
            }
            catch (e) {
                this.populateControlPanels().catch();
                console.log('Update error catch - '+ e);
            }
        }   
    }

    intervalUpdate() {
        this.refreshSignDisplays().catch();
    }

    render() {
        return (
            <div className="main-page">
                <h2>Annunciator Panels</h2>
                <NotificationContainer />
                {this.state.controlPanels
                    ? <div>
                        <div className="display-container">
                            <b id="title">Live Sign Displays</b>
                            <div className="display-content">
                                {this.state.controlPanels.map((panel) => {
                                    return (<SignDisplay key={panel} name={panel} ref={this[panel + "SignDisplay"]} />)
                                })}
                            </div>
                        </div>
                        <SignMessage controlPanels={this.state.controlPanels}/>
                    </div>
                    : <div>Loading ...</div>}
            </div>
        );
    }
}
/*
updateHandler={this.refreshSignDisplays}
*/
