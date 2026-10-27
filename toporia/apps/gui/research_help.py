"""Preset explanations in the existing shared Help window."""

from .help import HelpTopic


class ResearchHelpTopic(HelpTopic):
    """Retain the ordinary help contract, appending structured science content."""

    def __init__(self, topic, description):
        super().__init__(topic.title, list(topic.sections))
        self.description = description

    def to_html(self):
        from toporia.apps.research_render import description_html
        return super().to_html() + "\n" + description_html(self.description)
