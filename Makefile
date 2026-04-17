PYTHON  := uv run python
ZT      := $(PYTHON) -m zt.cli
EXAMPLES_DIR := examples
BUILD_DIR    := build

SINGLE_SOURCES := $(wildcard $(EXAMPLES_DIR)/*.fs)
SINGLE_SNAS    := $(patsubst $(EXAMPLES_DIR)/%.fs,$(BUILD_DIR)/%.sna,$(SINGLE_SOURCES))

MULTIFILE_ROOTS := sierpinski plasma
MULTIFILE_SNAS  := $(patsubst %,$(BUILD_DIR)/%.sna,$(MULTIFILE_ROOTS))

.PHONY: all examples test clean help

all: examples

help:
	@echo "targets:"
	@echo "  examples  build every example into $(BUILD_DIR)/ with matching .map"
	@echo "  test      run the pytest suite"
	@echo "  clean     remove $(BUILD_DIR)/"

examples: $(SINGLE_SNAS) $(MULTIFILE_SNAS)

$(BUILD_DIR)/%.sna: $(EXAMPLES_DIR)/%.fs | $(BUILD_DIR)
	$(ZT) build $< -o $@ --map $(@:.sna=.map)

$(BUILD_DIR)/sierpinski.sna: \
        $(EXAMPLES_DIR)/sierpinski/main.fs \
        $(wildcard $(EXAMPLES_DIR)/sierpinski/lib/*.fs) \
        | $(BUILD_DIR)
	$(ZT) build $< -o $@ --map $(@:.sna=.map)

$(BUILD_DIR)/plasma.sna: \
        $(EXAMPLES_DIR)/plasma/main.fs \
        $(wildcard $(EXAMPLES_DIR)/plasma/lib/*.fs) \
        $(wildcard $(EXAMPLES_DIR)/plasma/app/*.fs) \
        | $(BUILD_DIR)
	$(ZT) build $< -o $@ --map $(@:.sna=.map)

$(BUILD_DIR):
	mkdir -p $@

test:
	uv run pytest

clean:
	rm -rf $(BUILD_DIR)
