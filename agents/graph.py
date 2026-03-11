from agents.design_agent import run_design
from agents.dev_agent import run_dev
from agents.test_agent import run_tests
from agents.docs_agent import run_docs

def orchestrate(title, description):

    result = {}

    result.update(run_design(title, description))
    result.update(run_dev(result))
    result.update(run_tests(result))
    result.update(run_docs(result))

    return result
