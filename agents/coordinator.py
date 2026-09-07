import os

from agents.researcher import research
from agents.summarizer import summarize
from agents.evaluator import evaluate
from agents.notebook import Notebook
from agents.output import research_base, slugify
from agents.llm import keep_warm
from logger import log

MAX_ITERATIONS = 5


async def run_pipeline(topic, dir_name=None):
    await keep_warm()  # pin the local model so repeated runs skip the cold reload

    name = dir_name or slugify(topic)
    out_dir = os.path.join(research_base(), name)
    os.makedirs(out_dir, exist_ok=True)
    notebook = Notebook(out_dir, topic, name)

    notes = await research(topic, notebook)  # writes source notes as it gathers

    summary = await summarize(notes, topic)
    iteration = 1
    verdict = await evaluate(notes, summary, topic)

    while verdict != "APPROVED" and iteration < MAX_ITERATIONS:
        log("coordinator", {"iteration": iteration, "verdict": verdict, "action": "retrying summarizer"})
        summary = await summarize(notes, topic)
        verdict = await evaluate(notes, summary, topic)
        iteration += 1

    log("coordinator", {"finalIteration": iteration, "verdict": verdict})

    result = {
        "topic": topic,
        "notes": notes,
        "summary": summary,
        "iterations": iteration,
        "verdict": verdict,
    }

    output_dir = notebook.finalize(result)
    result["output_dir"] = output_dir
    log("coordinator", {"output_dir": output_dir})

    return result
