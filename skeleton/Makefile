
all: protobuf/skeleton/proto/Protobuf.proto
	@make -C protobuf
	@make -C src

run: all
	PYTHONPATH=.. python3 -m skeleton --debug

protobuf/skeleton/proto/Protobuf.proto:
	PYTHONPATH=.. python3 -m _.records.protobuf > $@
