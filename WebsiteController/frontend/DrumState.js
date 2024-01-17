import React, { Component } from 'react';
import { NotificationManager } from 'react-notifications';
import './SignDisplay.css'
import './DrumState.css'

// assumed timer isn't going to be longer then 59  mins
export default class DrumState extends Component {

    constructor(props) {
        super(props);
        this.name = props.name;
        this.state = {
            show: false,
            drumState: "",
            mins: 0,
            secs: 0,
            secs: 0,
            timerDetails: ""
        };
        this.update = this.update.bind(this);
    }

    componentWillUnmount() {
        clearInterval(this.timerID);
    }

    formatTimer() {
        var minutes = this.state.mins.toString();
        var seconds = this.state.secs.toString();
        minutes = minutes.length === 1 ? "0" + minutes : minutes;
        seconds = seconds.length === 1 ? "0" + seconds : seconds;
        return minutes + ':' + seconds;
    }

    decrementTimer() {
        var new_sec = this.state.secs - 1;
        var new_min = this.state.mins;
        if (new_sec < 0) {
            new_min = new_min - 1;
            if (new_min < 0) {
                new_min = 0;
                new_sec = 0;
                clearInterval(this.timerID);
            } else {
                new_sec = 59;
            }
        }

        this.setState({
            mins: new_min,
            secs: new_sec
        });
    }

    async update(drum) {
        //console.log(this.name);
        //console.log(JSON.stringify(drum));
   
        if (["isotimer"].includes(drum.state)) {
            
            var dur = drum.timerDuration.split(':');
            var dif = new Date() - Date.parse(drum.timerStart);
            console.log(drum.timerStart);
            let h, m, s;
            h = Math.floor((dif / (1000 * 60 * 60)) % 24);
            m = Math.floor((dif / (1000 * 60)) % 60);
            s = Math.floor((dif / 1000) % 60);

            console.log(h);
            console.log(m);
            console.log(s);

            var hours = parseInt(dur[0]) - Math.floor((dif / (1000 * 60 * 60)) % 24);
            var mins = parseInt(dur[1]) - Math.floor((dif / (1000 * 60)) % 60);
            var secs = parseInt(dur[2]) - Math.floor((dif / 1000) % 60);
            console.log(hours);
            console.log(mins);
            console.log(secs);
            if (hours !== 0 ) {
                mins = 0;
                secs = 0;
                console.log('Error invaild timer time');
            }

            this.setState({
                show: true,
                drumState: drum.state,
                mins: mins,
                secs: secs,
                timerDetails: drum.timerDetails
            });
            this.timerID = setInterval(() => this.decrementTimer(), 1000);
        }
        else {
            this.setState({
                show: true,
                drumState: drum.state
            });
        }
    }

    getDrumStateHtml(drumStage) {
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
            return (
                    <small id="isotimer">CLOSE
                        <br></br>
                        <small id="isotag">{this.state.timerDetails}</small>
                        <small id="isotime">{this.formatTimer()}</small>
                    </small> 
            );
        }
        else {
            return (<small id="unset">----</small>);
        }
    }

    getDrumLabel() {
        if (["1A", "2A", "3A"].includes(this.name)) {
            return (<span id="drum-labelA">{this.name.slice(1)}</span>)
        } else {
            return (<span id="drum-labelB">{this.name.slice(1)}</span>)
        }
    }

    render() {
        if (this.state.show) {
            return (
                <div className="drum-status">
                    {this.getDrumLabel()}
                    {this.getDrumStateHtml(this.state.drumState)}
                </div>
            )
        } else {
            return (<div className="drum"></div>)
        }
    }
}
/*

*/