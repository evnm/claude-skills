SKILLS_DIR := $(HOME)/.claude/skills
SKILLS := $(notdir $(wildcard $(CURDIR)/*/))

.PHONY: install
install:
	@mkdir -p $(SKILLS_DIR)
	@for skill in $(SKILLS); do \
		ln -sfn $(CURDIR)/$$skill $(SKILLS_DIR)/$$skill; \
		echo "Linked $$skill"; \
	done
