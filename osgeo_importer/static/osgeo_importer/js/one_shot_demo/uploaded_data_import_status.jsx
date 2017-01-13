// http://stackoverflow.com/questions/34243685/updating-state-every-x-seconds

var greenLightURL = '/static/osgeo_importer/img/one_shot_demo/green-light.png';
var redLightURL = '/static/osgeo_importer/img/one_shot_demo/red-light.png';
var orangeSpinnerURL = '/static/osgeo_importer/img/one_shot_demo/orange-spinner.gif';

var UploadedDataImportStatusWidget = React.createClass({
    getInitialState: function() {
        var s = {
            statusLocation: '/importer-api/data/<id>/import-status',
            statusId: null,
            files: {
                'notreally.gpkg': {
                    'notreally.gpkg': 'working',
                    'layer2.notreally.gpkg': 'success',
                },
                'someotherfile.gpkg': {
                    'layera': 'error',
                },
            },
        };
        return s
    },
    
    render: function() {
        var fileImportsRendered = [];
        for (var filename in this.state.files) {

            var layersRendered = [];
            var layerDetails = this.state.files[filename];

            for (var layerName in layerDetails) {
                var nameStyle = {
                    display: "inline-block",
                    width: "15em",
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
                        <div style={nameStyle}><img style={imgStyle} src={statusImgSrc}/>{layerName}:</div>
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
