SKILLS_DIR := $(HOME)/.claude/skills
SKILLS := $(shell find . -maxdepth 1 -mindepth 1 -type d -not -name '.*' -exec basename {} \;)

.PHONY: install
install:
	@mkdir -p $(SKILLS_DIR)
	@for skill in $(SKILLS); do \
		ln -sfn $(CURDIR)/$$skill $(SKILLS_DIR)/$$skill; \
		echo "Linked $$skill"; \
	done
