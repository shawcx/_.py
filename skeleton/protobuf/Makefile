PROTOC     = protoc
PROTOFLAGS = -I.
PYTHON_DIR = ..

PROTO_FILES := $(wildcard skeleton/proto/*.proto)
PB2_FILES   := $(patsubst %.proto, $(PYTHON_DIR)/%_pb2.py, $(PROTO_FILES))


all: $(PB2_FILES)
	@#

$(PYTHON_DIR)/%_pb2.py: %.proto $(PROTO_FILES)
	@echo $(PROTOC) $< '=>' $@
	@$(PROTOC) $(PROTOFLAGS) --python_out=$(PYTHON_DIR) $<

clean:

distclean: clean
	@rm -rf $(PB2_FILES)
