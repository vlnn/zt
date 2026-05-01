PYTHON  := uv run python
ZT      := $(PYTHON) -m zt.cli
EXAMPLES_DIR := examples
BUILD_DIR    := build


SINGLE_SOURCES := $(wildcard $(EXAMPLES_DIR)/*.fs)
SINGLE_SNAS    := $(patsubst $(EXAMPLES_DIR)/%.fs,$(BUILD_DIR)/%.sna,$(SINGLE_SOURCES))

MULTIFILE_DIRS := $(patsubst $(EXAMPLES_DIR)/%/main.fs,%,$(wildcard $(EXAMPLES_DIR)/*/main.fs))
MULTIFILE_SNAS := $(patsubst %,$(BUILD_DIR)/%.sna,$(MULTIFILE_DIRS))

BUILD_FLAGS_plasma-128k      := --target 128k --include-dir $(EXAMPLES_DIR)
BUILD_FLAGS_im2-music        := --target 128k --include-dir $(EXAMPLES_DIR)
BUILD_FLAGS_zlm-tinychat     := --target 128k
BUILD_FLAGS_zlm-tinychat-48k := --target 48k --origin 0x5C00 --rstack 0xFF80 --dstack 0xFFC0 --no-inline-next --no-stdlib

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

define MULTIFILE_RULE
$$(BUILD_DIR)/$(1).sna: $$(EXAMPLES_DIR)/$(1)/main.fs \
    $$(shell find $$(EXAMPLES_DIR)/$(1) -name '*.fs' -not -path '*/tests/*') \
    | $$(BUILD_DIR)
	$$(ZT) build $$< -o $$@ --map $$(@:.sna=.map) $$(BUILD_FLAGS_$(1))
endef

$(foreach d,$(MULTIFILE_DIRS),$(eval $(call MULTIFILE_RULE,$(d))))

$(BUILD_DIR):
	mkdir -p $@

test:
	uv run pytest

clean:
	rm -rf $(BUILD_DIR)
