from agents.researcher import research
from agents.summarizer import summarize
from agents.evaluator import evaluate
from agents.output import write_outputs
from logger import log

MAX_ITERATIONS = 5


async def run_pipeline(topic):
    notes = await research(topic)

    summary = await summarize(notes)
    iteration = 1
    verdict = await evaluate(notes, summary)

    while verdict != "APPROVED" and iteration < MAX_ITERATIONS:
        log("coordinator", {"iteration": iteration, "verdict": verdict, "action": "retrying summarizer"})
        summary = await summarize(notes)
        verdict = await evaluate(notes, summary)
        iteration += 1

    log("coordinator", {"finalIteration": iteration, "verdict": verdict})

    result = {
        "topic": topic,
        "notes": notes,
        "summary": summary,
        "iterations": iteration,
        "verdict": verdict,
    }

    output_dir = write_outputs(result)
    result["output_dir"] = output_dir
    log("coordinator", {"output_dir": output_dir})

    return result
