from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from treasury_data_engine import Base, TreasuryYield, is_data_upto_date


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_is_data_upto_date_none_reference():
    db = make_session()
    row = TreasuryYield(observation_date=date(2026, 1, 1), maturity="2Y", yield_value=1.23)
    db.add(row)
    db.commit()

    assert is_data_upto_date(db) is True


def test_is_data_upto_date_with_reference():
    db = make_session()
    row = TreasuryYield(observation_date=date(2026, 1, 1), maturity="2Y", yield_value=1.23)
    db.add(row)
    db.commit()

    assert is_data_upto_date(db, reference_date=date(2026, 1, 1)) is True
    assert is_data_upto_date(db, reference_date=date(2026, 2, 1)) is False
