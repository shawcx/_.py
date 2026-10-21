
PATH := $(PATH):/opt/homebrew/bin

BROWSERIFY = ./node_modules/.bin/browserify
SASS       = ./node_modules/.bin/sass

STATIC_ROOT = ../skeleton/static

JS_FILES := $(wildcard js/*.js js/*/*.js)
JS_FILE   = js/skeleton.js
JS_OUT    = $(STATIC_ROOT)/$(JS_FILE)

CSS_OUT = $(STATIC_ROOT)/css/skeleton.css
CSS_SRC = sass/skeleton.scss $(wildcard sass/*.scss)

SASS_FLAGS = -I ./node_modules/@fortawesome/fontawesome-free/scss \
             -I ./node_modules/bootstrap/scss

WEBFONTS_SRC = ./node_modules/@fortawesome/fontawesome-free/webfonts
WEBFONTS = $(STATIC_ROOT)/webfonts

LOGO    = $(STATIC_ROOT)/images/skeleton.png
FAVICON = $(STATIC_ROOT)/favicon.ico

all: node_modules $(JS_OUT) $(CSS_OUT) $(WEBFONTS) $(LOGO) $(FAVICON)
	@#

$(LOGO): images/skeleton.png
	@mkdir -p $(dir $@)
	@cp $< $@

$(FAVICON): images/favicon.ico
	@cp $< $@

# regenerate the committed images after editing the SVGs,
# needs rsvg-convert (librsvg) and ImageMagick
images:
	rsvg-convert -w 96 -h 96 images/skeleton.svg -o images/skeleton.png
	for s in 16 32 48; do rsvg-convert -w $$s -h $$s images/favicon.svg -o images/favicon-$$s.png; done
	convert images/favicon-16.png images/favicon-32.png images/favicon-48.png images/favicon.ico
	rm images/favicon-*.png

$(WEBFONTS): $(WEBFONTS_SRC)
	@cp -r $(WEBFONTS_SRC) $(STATIC_ROOT)

node_modules:
	@npm install .

$(JS_OUT): $(JS_FILES)
	@echo browserify $(JS_FILE) '=>' $@
	@$(BROWSERIFY) $(JS_FILE) -o $@

$(CSS_OUT): $(CSS_SRC)
	@echo sass $< '=>' $@
	@$(SASS) $(SASS_FLAGS) $< $@

.PHONY: images

clean:

distclean: clean
	@rm -vf $(CSS_OUT)
	@rm -vf $(JS_OUT)
	@rm -vf $(LOGO) $(FAVICON)
	@rm -rf node_modules
