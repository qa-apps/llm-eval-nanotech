import os
import pytest
from playwright.sync_api import Page, expect

deepeval = pytest.importorskip('deepeval', reason='deepeval not installed')
from deepeval import assert_test  # noqa: E402
from deepeval.metrics import GEval  # noqa: E402
from deepeval.test_case import LLMTestCase, SingleTurnParams  # noqa: E402
from pages.interactive_tools import InteractiveTools  # noqa: E402
from pages.landing_sections import LandingSections  # noqa: E402
from utils.nanotech_judge import NanotechJudge  # noqa: E402


pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(
        os.getenv('RUN_LLM_EVALS') != '1',
        reason='Set RUN_LLM_EVALS=1 to enable UI LLM judge runs.',
    ),
]


JUDGE = NanotechJudge()
BOT_MESSAGE_SELECTOR = '.chat-message.bot-message'
BOT_CONTENT_SELECTOR = '.chat-message.bot-message .message-content'
CHAT_INPUT_SELECTOR = (
    '#chat-input, textarea#chat-input, input#chat-input, '
    '.chat-input-area textarea, .chat-input-area input'
)
SEND_BUTTON_SELECTOR = (
    '#chat-form button.chat-send-btn, '
    '#chat-form button[aria-label="Send message"], '
    'button.chat-send-btn'
)


def _send_prompt_and_get_reply(page: Page, tools: InteractiveTools, prompt: str) -> str:
    tools.open_chat_window()
    tools.click_mode('General')
    input_box = page.locator(CHAT_INPUT_SELECTOR).first
    expect(input_box).to_be_visible(timeout=10_000)
    existing_messages = page.locator(BOT_MESSAGE_SELECTOR).count()
    input_box.fill(prompt)
    page.locator(SEND_BUTTON_SELECTOR).first.click()
    page.wait_for_function(
        "({selector, count}) => document.querySelectorAll(selector).length > count",
        arg={'selector': BOT_MESSAGE_SELECTOR, 'count': existing_messages},
        timeout=30_000,
    )
    reply = page.locator(BOT_CONTENT_SELECTOR).nth(existing_messages)
    expect(reply).to_be_visible(timeout=30_000)
    try:
        page.locator('.typing-indicator-msg').wait_for(state='hidden', timeout=30_000)
    except Exception:
        pass
    text = reply.inner_text().strip()
    assert text
    return text


def _case(prompt: str, reply: str) -> LLMTestCase:
    return LLMTestCase(input=prompt, actual_output=reply)


def _metric(name: str, criteria: str) -> GEval:
    rubric = (
        "Rate the response on a scale of 1 to 5, where: "
        "1 = absolute fail, "
        "2 = very fail, "
        "3 = mostly fail, "
        "4 = mostly pass, "
        "5 = absolute pass. "
        "A score of 4 or higher means the response meets expectations. "
        f"Evaluation focus: {criteria}"
    )
    return GEval(
        name=name,
        criteria=rubric,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        threshold=0.6,
        model=JUDGE,
    )


def _assert_reply_quality(
    page: Page,
    tools: InteractiveTools,
    prompt: str,
    name: str,
    criteria: str,
):
    reply = _send_prompt_and_get_reply(page, tools, prompt)
    assert_test(_case(prompt, reply), [_metric(name, criteria)])


class TestChatbotJudgeUi:
    @pytest.fixture(autouse=True)
    def on_home(self, landing: LandingSections):
        landing.goto_home()

    def test_logistics_operations_fit(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'We manage fleet dispatch and delayed shipments. How could NanoTech Hub help a logistics operation like ours?',
            'Logistics Operations Fit',
            'The response should stay business-focused, describe logistics-relevant automation such as dispatch, routing, tracking, or workflow agents, and offer a practical next step.',
        )

    def test_healthcare_admin_automation(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'We are a healthcare clinic buried in appointment scheduling, intake, and follow-up messages. What can you automate for us?',
            'Healthcare Admin Automation',
            'The response should focus on healthcare administrative automation, not diagnosis or treatment, and should mention practical workflows such as scheduling, intake, or patient communication.',
        )

    def test_ecommerce_support_automation(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'Our e-commerce team struggles with repetitive support tickets and return requests. What kind of AI solution would you build?',
            'E-commerce Support Automation',
            'The response should clearly connect to e-commerce support or returns workflows and suggest chatbots, agents, knowledge retrieval, or process automation that would reduce manual work.',
        )

    def test_finance_workflow_automation(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'We handle invoices, reconciliations, and compliance documents manually. How could AI help a finance team?',
            'Finance Workflow Automation',
            'The response should discuss finance or back-office workflow automation, document handling, or reconciliation support and must not drift into giving regulated financial advice.',
        )

    def test_mcp_integration_clarity(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'Explain MCP integrations in plain business language. Why would a company care?',
            'MCP Integration Clarity',
            'The response should explain MCP integrations in simple business language, connect them to real systems or tools, and make the value understandable to a non-technical buyer.',
        )

    def test_security_and_access_controls(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'We have sensitive internal data. How do you approach AI security and access controls on client projects?',
            'Security And Access Controls',
            'The response should acknowledge security, privacy, or access-control concerns carefully, stay business-focused, and avoid inventing unsupported certifications or guarantees.',
        )

    def test_discovery_process_quality(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'What happens in the first two weeks if we start an AI automation project with NanoTech Hub?',
            'Discovery Process Quality',
            'The response should describe a realistic early engagement process such as discovery, requirements gathering, workflow review, roadmap planning, or prototype definition, and it should provide a clear next step.',
        )

    def test_multichannel_assistant_relevance(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'Can you help a global support team with a multilingual AI assistant across email and chat?',
            'Multichannel Assistant Relevance',
            'The response should address multilingual or multichannel support, stay relevant to business automation, and explain how an assistant or agent could help across email and chat.',
        )

    def test_roi_framing(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'How would you estimate ROI for automating repetitive operations tasks?',
            'ROI Framing',
            'The response should discuss ROI in a grounded business way, such as measuring time saved, cost reduction, throughput, or baseline workflows, and should avoid making unrealistic guaranteed claims.',
        )

    def test_existing_stack_integration(self, page: Page, tools: InteractiveTools):
        _assert_reply_quality(
            page,
            tools,
            'We use Slack, Google Drive, and internal docs. Can you build something that works with our existing stack?',
            'Existing Stack Integration',
            'The response should confirm integration-oriented thinking, mention working with existing tools or knowledge sources, and frame the solution as fitting into a real business stack rather than replacing everything.',
        )
