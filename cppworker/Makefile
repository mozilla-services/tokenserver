PROJECT = tokencppworker
BUILD = build/
LIB = libs/
SRC = src/
OBJ = $(BUILD)main.o
LIBS = cryptopp
CPP = g++
CXXFLAGS = -Wall -ansi -pedantic-errors

all: mkdirs
	$(CPP) -c $(SRC)main.cpp -L $(LIB) -o $(BUILD)main.o $(CXXFLAGS) -lcryptopp
	$(CPP) $(OBJ) -l$(LIBS) -lpthread -o $(BUILD)$(PROJECT) $(CXXFLAGS) 

mkdirs:
	@if [ ! -d "$(BUILD)" ]; then \
		mkdir $(BUILD); \
	fi

clean:
	rm -rf $(BUILD)
