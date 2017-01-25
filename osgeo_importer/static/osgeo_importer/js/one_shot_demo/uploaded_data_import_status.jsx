// http://stackoverflow.com/questions/34243685/updating-state-every-x-seconds
var greenLightURL = '/static/osgeo_importer/img/one_shot_demo/green-light.png';
var redLightURL = '/static/osgeo_importer/img/one_shot_demo/red-light.png';
var orangeSpinnerURL = '/static/osgeo_importer/img/one_shot_demo/orange-spinner.gif';

function findGetParameter(parameterName) {
    var result = null,
        tmp = [];
    location.search
    .substr(1)
        .split("&")
        .forEach(function (item) {
        tmp = item.split("=");
        if (tmp[0] === parameterName) result = decodeURIComponent(tmp[1]);
    });
    return result;
}

var UploadedDataImportStatusWidget = React.createClass({
    getInitialState: function() {
        var uploadDataId = findGetParameter('uploadDataId');
        
        console.log('uploadDataId: ' + uploadDataId);
        if (uploadDataId != null) {
            setInterval(this.getStatus, 3000);
        }
        
        var s = {
            statusLocation: '/upload-data-import-status/' + uploadDataId,
            uploadDataId: uploadDataId,
            files: null,
        };
                
        return s
    },

    getStatus: function() {
        console.log('getStatus() entered');
        if (this.state.uploadDataId == null) {
            console.log('no uploadDataId');
            return;
        }
        var statusURL = this.state.statusLocation.replace('<id>', this.state.uploadDataId);
        var successCallback = this.statusChangeCallback;
        
        fetch(statusURL, {
            method: 'GET',
            headers: {
                'content-type': 'application/json',
            },
        })
        .then(
            function(resp) {
                if (resp.status != 200) {
                    console.log('Problem with ' + authURL + ', status: ' + resp.status);
                    return;
                }
                console.log('Got response:');
                console.log(resp);
                resp.json().then(successCallback).catch(function(err) {
                    console.log('fetch problem: ' + err);
                });
/*
                resp.json().then(function(data) {
                    console.log('json data:'); console.log(data); 
                }).catch(function(err) {
                    console.log('fetch problem: ' + err);
                });
*/
            }
        ).catch(function(err) { console.log('fetch problem: ' + err); });        
    },

    statusChangeCallback: function(jsonData) {
        console.log('statusChangeCallback entered');
        console.log('jsonData:');
        console.log(jsonData);
        this.setState({files: jsonData});
    },
    
    render: function() {
        if (this.state.uploadDataId == null) {
            return (<p>empty</p>);
        }
        
        var fileImportsRendered = [];
        for (var filename in this.state.files) {

            var layersRendered = [];
            var layerDetails = this.state.files[filename];

            for (var layerName in layerDetails) {
                var nameStyle = {
                    display: "inline-block",
                };
                
                var imgStyle = {
                    width: "1em",
                    margin: "0 0.5em 0 0.5em",
                };
                
                var status = layerDetails[layerName];
                
                var statusImgSrcLookup = {
                    working: orangeSpinnerURL,
                    success: greenLightURL,
                    error: redLightURL,
                }
                var statusImgSrc = statusImgSrcLookup[status];
                 
                layersRendered.push(
                    <div key={layerName}>
                        <div style={nameStyle}><img style={imgStyle} src={statusImgSrc}/>{layerName}</div>
                    </div>
                );
            }

            var filenameStyle = {
                marginTop: "0.5em",
            };
            fileImportsRendered.push(<div key={filename} style={filenameStyle}>{filename}: {layersRendered}</div>);
        }
        
        return (
            <div>{fileImportsRendered}</div>
        );
    },    
});

ReactDOM.render(<UploadedDataImportStatusWidget />, document.getElementById('import-status'));
