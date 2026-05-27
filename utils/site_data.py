from typing import List, TypedDict

class LinkExpectation(TypedDict, total=False):
    label: str
    expectedUrlPart: str
    expectedText: str

class DropdownGroup(TypedDict):
    menuLabel: str
    links: List[LinkExpectation]

header_dropdowns: List[DropdownGroup] = [
    {
        'menuLabel': 'Solutions',
        'links': [
            {'label': 'AI Process Automation'},
            {'label': 'Multi-Agent Orchestration'},
            {'label': 'Predictive Analytics'},
            {'label': 'Document Intelligence'},
            {'label': 'Conversational AI'},
            {'label': 'AI Quality Assurance'},
            {'label': 'Knowledge Management'},
            {'label': 'Workflow Optimization'},
            {'label': 'Computer Vision'},
            {'label': 'Custom LLM Development'}
        ]
    },
    {
        'menuLabel': 'Services',
        'links': [
            {'label': 'AI Consulting & Strategy'},
            {'label': 'MCP Development'},
            {'label': 'AI Agent Development'},
            {'label': 'RAG Implementation'},
            {'label': 'API Integration'},
            {'label': 'ML Model Training'},
            {'label': 'Data Engineering'},
            {'label': 'AI Testing & Automation'},
            {'label': 'Cloud AI Deployment'},
            {'label': 'AI Maintenance & Support'}
        ]
    },
    {
        'menuLabel': 'Industries',
        'links': [
            {'label': 'Finance & Banking'},
            {'label': 'Healthcare'},
            {'label': 'Insurance'},
            {'label': 'Legal & Compliance'},
            {'label': 'Retail & E-Commerce'},
            {'label': 'Manufacturing'},
            {'label': 'Logistics & Supply Chain'},
            {'label': 'Real Estate'},
            {'label': 'Education & E-Learning'},
            {'label': 'Energy & Utilities'}
        ]
    },
    {
        'menuLabel': 'Technologies',
        'links': [
            {'label': 'LangChain & LangGraph'},
            {'label': 'CrewAI & AutoGen'},
            {'label': 'OpenAI Agents SDK'},
            {'label': 'Vector Databases'},
            {'label': 'Model Context Protocol'},
            {'label': 'HuggingFace & Transformers'},
            {'label': 'PyTorch & TensorFlow'},
            {'label': 'Kubernetes & MLOps'},
            {'label': 'Graph Neural Networks'},
            {'label': 'Edge AI & On-Device'}
        ]
    },
    {
        'menuLabel': 'Resources',
        'links': [
            {'label': 'Case Studies'},
            {'label': 'AI Readiness Assessment'},
            {'label': 'Whitepapers'},
            {'label': 'Blog & Insights'},
            {'label': 'AI Glossary'},
            {'label': 'Webinars & Events'},
            {'label': 'ROI Calculator'},
            {'label': 'FAQ'},
            {'label': 'Implementation Guide'},
            {'label': 'Partner Program'}
        ]
    }
]

footer_link_labels = [
    'Process Automation',
    'Custom AI Development',
    'AI Integration',
    'AI Strategy Consulting',
    'About Us',
    'Industries',
    'ROI & Benefits',
    'Contact',
    'AI Assessment',
    'ROI Calculator',
    'Case Studies',
    'Get Demo'
]

key_content_texts = [
    'Autonomous Agent Services',
    'ROI & Benefits',
    'Start Your AI Transformation',
    'Leading AI Automation & Intelligence',
    'AI Solutions Across Sectors',
    'Measurable Business Impact'
]

industries = [
    'Financial Services', 'Healthcare', 'Manufacturing',
    'Retail & E-commerce', 'Logistics & Transport', 'Professional Services'
]

services = [
    'Agentic Process Automation', 'AI Agent Development',
    'AI Agent Orchestration & Integration', 'Business Process Analysis',
    'AI Testing & Quality Assurance', 'AI Strategy Consulting'
]

tech_keywords = [
    'Agentic AI', 'Large Language Models', 'Machine Learning',
    'Computer Vision', 'Big Data', 'Data Analytics',
    'Natural Language Processing', 'Generative AI', 'Multi-Agent Systems'
]

form_service_options = [
    'Process Automation (RPA + AI)',
    'Custom AI Model Development',
    'AI Integration & Implementation',
    'Business Process Analysis',
    'AI Testing & Quality Assurance',
    'AI Strategy Consulting'
]
