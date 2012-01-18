PROJECT = tokencppworker
BUILD = build/
LIB = libs/
SRC = src/
LIBS = cryptopp
CPP = g++
PROTOBUF = $(SRC)
CXXFLAGS = -Wall -ansi -pedantic-errors

all: mkdirs protobuf libhose
	$(CPP) -o $(BUILD)$(PROJECT) $(SRC)response.pb.cc $(SRC)crypto.cpp $(SRC)libhose.o -lprotobuf -lzmq -lcryptopp $(CXXFLAGS)

protobuf:
	cd $(SRC); protoc response.proto --cpp_out=. --python_out=../client

mkdirs:
	@if [ ! -d "$(BUILD)" ]; then \
		mkdir $(BUILD); \
	fi

libhose:
	cp ../../powerhose/powerhose/libhose/libhose.o src
	cp ../../powerhose/powerhose/libhose/libhose.h src

clean:
	rm -rf $(BUILD)
	rm src/libhose.o src/libhose.h
