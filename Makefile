PROTOC := protoc
PROTOFLAGS := -I. -I`pkg-config protobuf --variable=includedir`

# find all proto files in the records protobuf directory
PROTO_FILES := $(wildcard _/records/*.proto)
PB2_FILES   := $(patsubst %.proto, %_pb2.py, $(PROTO_FILES))


all: $(PB2_FILES)
	@#

install: all
	pip3 install --upgrade .

dist: all
	@./setup.py sdist

%_pb2.py: %.proto $(PROTO_FILES)
	@echo $(PROTOC) $< '=>' $@
	@$(PROTOC) $(PROTOFLAGS) --python_out=. $<

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@rm -f $(PB2_FILES)

distclean: clean
	@rm -rf build/ dist/ *.egg-info/
