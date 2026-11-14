from patra.extract import RuleProfileExtractor
from patra.link import link_schemes

extractor = RuleProfileExtractor()


def test_age_and_income():
    e = extractor.extract("I am 45 years old and my annual income is 1.5 lakh")
    assert e.profile["age"] == 45
    assert e.profile["income_annual"] == 150000


def test_negated_income_tax_is_no():
    e = extractor.extract("I do not pay income tax")
    assert e.profile["income_tax_payer"] == "no"


def test_affirmed_income_tax_is_yes():
    e = extractor.extract("I pay income tax every year")
    assert e.profile["income_tax_payer"] == "yes"


def test_gender_and_category():
    e = extractor.extract("I am a woman with a BPL card")
    assert e.profile["gender"] == "F"
    assert e.profile["category"] == "BPL"


def test_residence():
    assert extractor.extract("we live in a village").profile["residence"] == "rural"
    assert extractor.extract("we live in a city").profile["residence"] == "urban"


def test_marks():
    assert extractor.extract("I scored 72 percent marks").profile["marks"] == 72.0


def test_linking_english_and_hindi():
    assert link_schemes("Am I eligible for PM-KISAN?")[0] == "pmkisan"
    assert link_schemes("क्या मुझे उज्ज्वला कनेक्शन मिल सकता है?")[0] == "pmuy"


def test_linking_returns_empty_for_unknown_scheme():
    assert link_schemes("Am I eligible for the Kerala widow pension?") == []
