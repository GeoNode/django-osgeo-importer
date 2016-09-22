.PHONY: all clean js css

all: js css

clean: 
	rm -rf node_modules
	rm -rf js
	rm css/angular-wizard.min.css

node_modules:
	npm install --no-optional

js: node_modules
	mkdir -p js
	# cp node_modules/angular/angular.min.js dist_js/
	cp node_modules/angular/angular.js js/
	# cp node_modules/angular-cookies/angular-cookies.min.js js/
	cp node_modules/angular-cookies/angular-cookies.js js/
	# cp node_modules/angular-resource/angular-resource.min.js js/
	cp node_modules/angular-resource/angular-resource.js js/
	cp node_modules/angular-file-upload/dist/angular-file-upload.min.js js/
	cp node_modules/angular-wizard/dist/angular-wizard.min.js js/
	cp node_modules/angular-ui-bootstrap/ui-bootstrap-tpls.min.js js/ui-bootstrap-tpls-0.14.2.min.js
	cp node_modules/underscore/underscore-min.js js/

css: node_modules
	mkdir -p css
	cp node_modules/angular-wizard/dist/angular-wizard.min.css css/
