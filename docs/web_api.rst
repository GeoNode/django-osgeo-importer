**********************
Web API REST Interface
**********************

Resources:
==========

UploadedLayer
-------------
  * [get] /importer-api/data-layers/[<id>] - list all for user or get detail for specific instance
  * [post] /importer-api/data-layers/<id>/configure/ - Import this layer.  Essentially calls all import handlers set up in settings.
    Parameters are passed in the body of the request as json and typically look something like this::

        {
            "configureTime": false,
            "convert_to_date: [],
            "editable": true,
            "end_date": null,
            "geoserver_store": { "type": "geogig" },
            "index": 0,
            "name": "new_layer_name",
            "permissions": {
                "users": {
                    "AnonymousUser": [
                        "change_layer_data", "download_resourcebase", "view_resourcebase"
                    ]
                }
            },
            "start_date": null
        }

UploadedData
------------
urls:
   * [get] /importer-api/data/[<id>] - list all for user or get detail for specific instance
   * [delete] /importer-api/data/<id> 
   * [post] /importer-api/data/<id>/import_all_layers/ - import all layers that belong to this instance.
     This is like calling /importer-api/data-layers/<id>/configure/ for all layers with a default configuration.
   
UploadedFile
------------
 - urls:
   * [put] /importer-api/file-upload/ - typical multipart/form-data file upload name="file" filename="<name of file>"
