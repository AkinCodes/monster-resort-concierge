import pytest
from app.ragas_eval import evaluate_rag_batch


@pytest.mark.skipif(True, reason="RAGAS eval requires OpenAI API key for LLM-based metrics")
def test_ragas_eval_example():
    """Test RAGAS evaluation with sample Q&A pairs."""
    samples = [
        {
            "question": "What time is check in?",
            "answer": "Check-in is from 3pm.",
            "contexts": ["Check-in is from 3pm to midnight."],
            "reference": "Check-in starts at 3pm"
        },
    ]
    results = evaluate_rag_batch(samples)
    assert "faithfulness" in results


@pytest.mark.skipif(True, reason="RAGAS eval requires OpenAI API key for LLM-based metrics")
def test_ragas_eval_with_poor_answer():
    """Test RAGAS with intentionally poor answer to verify scoring."""
    samples = [
        {
            "question": "What time is check in?",
            "answer": "The sky is blue.",
            "contexts": ["Check-in is from 3pm to midnight."],
            "reference": "Check-in starts at 3pm"
        }
    ]
    results = evaluate_rag_batch(samples)
    assert "faithfulness" in results


@pytest.mark.skipif(True, reason="RAGAS eval requires OpenAI API key for LLM-based metrics")
def test_ragas_eval_batch_format():
    """Test that evaluate_rag_batch accepts the correct format."""
    samples = [
        {
            "question": "Test question?",
            "answer": "Test answer.",
            "contexts": ["Test context."],
            "reference": "Test reference"
        }
    ]
    results = evaluate_rag_batch(samples)
    assert isinstance(results, dict)
