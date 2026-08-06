"""Unit tests for Fake News Detector. Run with: pytest tests/ -v"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.model import DataProcessor, ModelTrainer

class TestDataProcessor:
    def setup_method(self):
        self.processor = DataProcessor()

    def test_preprocess_returns_array(self):
        result = self.processor.preprocess([1, 2, 3])
        assert result is not None and len(result) == 3

    def test_postprocess_returns_list(self):
        import numpy as np
        result = self.processor.postprocess(np.array([0.9, 0.3, 0.6]))
        assert isinstance(result, list) and len(result) == 3

    def test_labels(self):
        assert self.processor._get_label(0.9) == "positive"
        assert self.processor._get_label(0.5) == "neutral"
        assert self.processor._get_label(0.1) == "negative"

class TestModelTrainer:
    def setup_method(self):
        self.trainer = ModelTrainer(model_path="/tmp/test_models/")

    def test_evaluate_returns_metrics(self):
        metrics = self.trainer.evaluate([], [])
        assert "accuracy" in metrics and 0 <= metrics["accuracy"] <= 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
