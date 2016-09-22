.PHONY: all clean dist_js dist_css

all: dist_js dist_css

clean: 
	rm -rf node_modules
	rm -rf dist_js
	rm -rf dist_css

node_modules:
	npm install --no-optional

dist_js: node_modules
	mkdir -p dist_js
	# cp node_modules/angular/angular.min.js dist_js/
	cp node_modules/angular/angular.js dist_js/
	# cp node_modules/angular-cookies/angular-cookies.min.js dist_js/
	cp node_modules/angular-cookies/angular-cookies.js dist_js/
	# cp node_modules/angular-resource/angular-resource.min.js dist_js/
	cp node_modules/angular-resource/angular-resource.js dist_js/
	cp node_modules/angular-file-upload/dist/angular-file-upload.min.js dist_js/
	cp node_modules/angular-wizard/dist/angular-wizard.min.js dist_js/
	cp node_modules/angular-ui-bootstrap/ui-bootstrap-tpls.min.js dist_js/ui-bootstrap-tpls-0.14.2.min.js
	cp node_modules/underscore/underscore-min.js dist_js/

dist_css: node_modules
	mkdir -p dist_css
	cp node_modules/angular-wizard/dist/angular-wizard.min.css dist_css/
