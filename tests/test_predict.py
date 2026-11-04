
import pytest
from unittest.mock import Mock

from src.predict import (
    predict,
    InputValidationError,
    MAX_TEXT_LENGTH,
)


@pytest.fixture
def mock_model():
    model = Mock()
    model.predict.return_value = [0]
    return model


# Положительный тест
def test_valid_input(mock_model):
    result = predict(
        {"text": "What is machine learning?"},
        model=mock_model,
    )

    assert result == {
        "label": 0,
        "class_name": "BENIGN",
    }
    mock_model.predict.assert_called_once_with(
        ["What is machine learning?"]
    )


# Негативный тест 1: неверный тип
def test_invalid_type(mock_model):
    with pytest.raises(InputValidationError):
        predict({"text": 123}, model=mock_model)

    mock_model.predict.assert_not_called()


# Негативный тест 2: пустая строка
def test_empty_text(mock_model):
    with pytest.raises(InputValidationError):
        predict({"text": ""}, model=mock_model)

    mock_model.predict.assert_not_called()


# Негативный тест 3: превышение лимита
def test_text_too_long(mock_model):
    text = "A" * (MAX_TEXT_LENGTH + 1)

    with pytest.raises(InputValidationError):
        predict({"text": text}, model=mock_model)

    mock_model.predict.assert_not_called()


# Негативный тест 4: отсутствует поле
def test_missing_field(mock_model):
    with pytest.raises(InputValidationError):
        predict({}, model=mock_model)

    mock_model.predict.assert_not_called()


# Негативный тест 5: неизвестное поле
def test_unexpected_field(mock_model):
    with pytest.raises(InputValidationError):
        predict(
            {"text": "Hello", "admin": True},
            model=mock_model,
        )

    mock_model.predict.assert_not_called()


# Негативный тест 6: нулевой байт
def test_null_byte(mock_model):
    with pytest.raises(InputValidationError):
        predict(
            {"text": "Hello\x00World"},
            model=mock_model,
        )

    mock_model.predict.assert_not_called()


# Негативный тест 7: некорректная структура
def test_invalid_structure(mock_model):
    with pytest.raises(InputValidationError):
        predict(["Hello"], model=mock_model)

    mock_model.predict.assert_not_called()


# Негативный тест 8: значение None
def test_none_input(mock_model):
    with pytest.raises(InputValidationError):
        predict({"text": None}, model=mock_model)

    mock_model.predict.assert_not_called()
