"""Independent Dixon-Coles adapter, sharing ONLY historical result rows."""
from multimodel_v2.dixon_coles_shadow import forecast_dixon_coles

def predict_dixon_coles(history, fixture, *, frozen_at_utc):
    row = forecast_dixon_coles(history, fixture, frozen_at_utc=frozen_at_utc,
                              model_version="callumfm-dixon-coles-v1",
                              min_matches=30, xg_weight=1.0)
    return dict(row, probability_status="uncalibrated_research")
