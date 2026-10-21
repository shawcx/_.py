
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

all: node_modules $(JS_OUT) $(CSS_OUT) $(WEBFONTS)
	@#

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

clean:

distclean: clean
	@rm -vf $(CSS_OUT)
	@rm -vf $(JS_OUT)
	@rm -rf node_modules
