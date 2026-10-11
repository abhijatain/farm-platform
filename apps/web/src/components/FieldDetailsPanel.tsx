import { useEffect, useMemo, useState } from "react";

import { Plus, X } from "lucide-react";

import {
  createActivity,
  createCropCycle,
  getFieldTimeline,
  harvestCropCycle,
  listSatelliteObservations,
} from "../lib/api";

import SatelliteHealthCard from "./SatelliteHealthCard";

import type {
  CropCycle,
  Farm,
  Field,
  SatelliteObservation,
  Season,
  TimelineItem,
} from "../types/api";

type Props = {
  farm: Farm;

  field: Field;

  season: Season | null;

  cropCycle: CropCycle | null;

  onClose: () => void;

  onDataChanged: () => Promise<void>;
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

function currentDateTime() {
  const now = new Date();

  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);

  return local.toISOString().slice(0, 16);
}

export default function FieldDetailsPanel({
  field,
  season,
  cropCycle,
  onClose,
  onDataChanged,
}: Props) {
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);

  const [loading, setLoading] = useState(true);

  const [cropForm, setCropForm] = useState(false);

  const [activityForm, setActivityForm] = useState(false);

  const [harvestForm, setHarvestForm] = useState(false);
  const [satelliteObservations, setSatelliteObservations] = useState<
    SatelliteObservation[]
  >([]);

  const [satelliteLoading, setSatelliteLoading] = useState(true);
  async function loadSatelliteObservations() {
    try {
      setSatelliteLoading(true);

      const result = await listSatelliteObservations(field.id);

      setSatelliteObservations(result);
    } finally {
      setSatelliteLoading(false);
    }
  }

  async function loadTimeline() {
    try {
      setLoading(true);

      const result = await getFieldTimeline(field.id);

      setTimeline(result);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadTimeline();

    void loadSatelliteObservations();
  }, [field.id]);
  /*
   * Only show timeline items for
   * the selected season.
   */
  const visibleTimeline = useMemo(() => {
    if (!season) {
      return [];
    }

    return timeline.filter((item) => item.season_id === season.id);
  }, [timeline, season]);

  async function refreshAll() {
    await onDataChanged();

    await loadTimeline();
  }

  const yieldPerAcre =
    cropCycle?.yield_kg != null &&
    cropCycle.harvested_area_acres != null &&
    cropCycle.harvested_area_acres > 0
      ? cropCycle.yield_kg / cropCycle.harvested_area_acres
      : null;

  const estimatedValue =
    cropCycle?.yield_kg != null && cropCycle.selling_price_per_kg != null
      ? cropCycle.yield_kg * cropCycle.selling_price_per_kg
      : null;

  return (
    <aside className="field-panel">
      <div className="field-panel-header">
        <div>
          <h2>{field.name}</h2>

          <span>
            {field.area_hectares.toFixed(2)}
            {" ha · "}
            {field.area_acres.toFixed(2)}
            {" acres"}
          </span>
        </div>

        <button className="panel-close" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      {!season ? (
        <div className="crop-card">
          <span className="section-label">SEASON</span>

          <h3>No season selected</h3>

          <p>Create or select a season before starting a crop.</p>
        </div>
      ) : (
        <>
          <section className="crop-card">
            <span className="section-label">{season.name.toUpperCase()}</span>

            {cropCycle ? (
              <>
                <h3>
                  {cropCycle.crop_name}

                  {cropCycle.variety ? ` · ${cropCycle.variety}` : ""}
                </h3>

                <p>Started {cropCycle.started_on}</p>

                <p>
                  Status: <strong>{cropCycle.status}</strong>
                </p>

                {cropCycle.status === "completed" && (
                  <div className="harvest-summary">
                    {cropCycle.yield_kg != null && (
                      <div>
                        <span>Total yield</span>

                        <strong>
                          {cropCycle.yield_kg.toLocaleString("en-IN")}
                          {" kg"}
                        </strong>
                      </div>
                    )}

                    {yieldPerAcre != null && (
                      <div>
                        <span>Yield / acre</span>

                        <strong>
                          {yieldPerAcre.toFixed(0)}
                          {" kg/ac"}
                        </strong>
                      </div>
                    )}

                    {cropCycle.harvested_on && (
                      <div>
                        <span>Harvested</span>

                        <strong>{cropCycle.harvested_on}</strong>
                      </div>
                    )}

                    {cropCycle.moisture_percent != null && (
                      <div>
                        <span>Moisture</span>

                        <strong>
                          {cropCycle.moisture_percent}
                          {"%"}
                        </strong>
                      </div>
                    )}

                    {cropCycle.quality_grade && (
                      <div>
                        <span>Quality</span>

                        <strong>{cropCycle.quality_grade}</strong>
                      </div>
                    )}

                    {cropCycle.selling_price_per_kg != null && (
                      <div>
                        <span>Price</span>

                        <strong>
                          ₹{cropCycle.selling_price_per_kg}
                          /kg
                        </strong>
                      </div>
                    )}

                    {estimatedValue != null && (
                      <div>
                        <span>Estimated value</span>

                        <strong>
                          ₹
                          {estimatedValue.toLocaleString("en-IN", {
                            maximumFractionDigits: 0,
                          })}
                        </strong>
                      </div>
                    )}
                  </div>
                )}

                {cropCycle.harvest_notes && (
                  <p className="harvest-notes">{cropCycle.harvest_notes}</p>
                )}

                {cropCycle.status === "active" && (
                  <button
                    className="harvest-button"
                    onClick={() => setHarvestForm(true)}
                  >
                    Record harvest
                  </button>
                )}
              </>
            ) : (
              <>
                <h3>No crop</h3>

                <p>No crop has been started on this field for {season.name}.</p>

                <button
                  className="secondary-action full"
                  onClick={() => setCropForm(true)}
                >
                  <Plus size={16} />
                  Start crop
                </button>
              </>
            )}
          </section>

          {cropCycle && cropCycle.status === "active" && (
            <button
              className="primary-action full"
              onClick={() => setActivityForm(true)}
            >
              <Plus size={17} />
              Add activity
            </button>
          )}
          <SatelliteHealthCard
            observations={satelliteObservations}
            loading={satelliteLoading}
          />

          <section className="timeline-section">
            <h3>{season.name} timeline</h3>

            {loading && <p className="dialog-muted">Loading…</p>}

            {!loading &&
              visibleTimeline.map((item) => (
                <div key={item.id} className="timeline-item">
                  <div className="timeline-dot" />

                  <div>
                    <strong>{item.activity_type}</strong>

                    <span>{new Date(item.occurred_at).toLocaleString()}</span>

                    {item.crop_name && (
                      <span>
                        {item.crop_name}

                        {item.variety ? ` · ${item.variety}` : ""}
                      </span>
                    )}

                    {item.notes && <p>{item.notes}</p>}
                  </div>
                </div>
              ))}

            {!loading && visibleTimeline.length === 0 && (
              <p className="dialog-muted">
                Nothing recorded for this season yet.
              </p>
            )}
          </section>
        </>
      )}

      {season && cropForm && (
        <StartCropDialog
          field={field}
          season={season}
          onClose={() => setCropForm(false)}
          onSaved={refreshAll}
        />
      )}

      {cropCycle && cropCycle.status === "active" && activityForm && (
        <ActivityDialog
          field={field}
          cropCycle={cropCycle}
          onClose={() => setActivityForm(false)}
          onSaved={refreshAll}
        />
      )}

      {cropCycle && cropCycle.status === "active" && harvestForm && (
        <HarvestDialog
          field={field}
          cropCycle={cropCycle}
          onClose={() => setHarvestForm(false)}
          onSaved={refreshAll}
        />
      )}
    </aside>
  );
}

function StartCropDialog({
  field,
  season,
  onClose,
  onSaved,
}: {
  field: Field;

  season: Season;

  onClose: () => void;

  onSaved: () => Promise<void>;
}) {
  const [cropName, setCropName] = useState("");

  const [variety, setVariety] = useState("");

  const [startedOn, setStartedOn] = useState(today());

  const [plantedOn, setPlantedOn] = useState("");

  const [saving, setSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!cropName.trim()) {
      setError("Crop name is required.");

      return;
    }

    try {
      setSaving(true);
      setError(null);

      await createCropCycle(season.id, {
        field_id: field.id,

        crop_name: cropName.trim(),

        variety: variety.trim() || null,

        started_on: startedOn,

        planted_on: plantedOn || null,

        expected_harvest_on: null,

        notes: null,
      });

      await onSaved();

      onClose();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Unable to start crop.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="dialog-card">
        <h2>Start crop</h2>

        <p className="dialog-muted">
          {field.name}
          {" · "}
          {season.name}
        </p>

        <label>Crop</label>

        <input
          className="form-input"
          value={cropName}
          onChange={(event) => setCropName(event.target.value)}
          placeholder="Paddy"
        />

        <label>Variety</label>

        <input
          className="form-input"
          value={variety}
          onChange={(event) => setVariety(event.target.value)}
          placeholder="PR-126"
        />

        <label>Crop cycle started</label>

        <input
          className="form-input"
          type="date"
          value={startedOn}
          onChange={(event) => setStartedOn(event.target.value)}
        />

        <label>Sowing / transplanting date</label>

        <input
          className="form-input"
          type="date"
          value={plantedOn}
          onChange={(event) => setPlantedOn(event.target.value)}
        />

        {error && <div className="login-error">{error}</div>}

        <div className="dialog-actions">
          <button className="secondary-action" onClick={onClose}>
            Cancel
          </button>

          <button className="primary-action" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Start crop"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ActivityDialog({
  field,
  cropCycle,
  onClose,
  onSaved,
}: {
  field: Field;

  cropCycle: CropCycle;

  onClose: () => void;

  onSaved: () => Promise<void>;
}) {
  const [activityType, setActivityType] = useState("irrigation");

  const [occurredAt, setOccurredAt] = useState(currentDateTime());

  const [notes, setNotes] = useState("");

  const [product, setProduct] = useState("");

  const [quantity, setQuantity] = useState("");

  const [unit, setUnit] = useState("");

  const [duration, setDuration] = useState("");

  const [source, setSource] = useState("");

  const [saving, setSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const inputActivity = [
    "fertilizer",
    "herbicide",
    "pesticide",
    "fungicide",
  ].includes(activityType);

  async function save() {
    const details: Record<string, unknown> = {};

    if (activityType === "irrigation") {
      if (duration) {
        details.duration_minutes = Number(duration);
      }

      if (source.trim()) {
        details.source = source.trim();
      }
    }

    if (inputActivity) {
      if (product.trim()) {
        details.product = product.trim();
      }

      if (quantity) {
        details.quantity = Number(quantity);
      }

      if (unit.trim()) {
        details.unit = unit.trim();
      }
    }

    try {
      setSaving(true);
      setError(null);

      await createActivity(field.id, {
        crop_cycle_id: cropCycle.id,

        activity_type: activityType,

        occurred_at: new Date(occurredAt).toISOString(),

        notes: notes.trim() || null,

        details,
      });

      await onSaved();

      onClose();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Unable to save activity.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="dialog-card">
        <h2>Add activity</h2>

        <p className="dialog-muted">
          {cropCycle.crop_name}

          {cropCycle.variety ? ` · ${cropCycle.variety}` : ""}
        </p>

        <label>Activity</label>

        <select
          className="form-input"
          value={activityType}
          onChange={(event) => setActivityType(event.target.value)}
        >
          <option value="irrigation">Irrigation</option>

          <option value="sowing">Sowing</option>

          <option value="transplanting">Transplanting</option>

          <option value="fertilizer">Fertilizer</option>

          <option value="herbicide">Herbicide</option>

          <option value="pesticide">Pesticide</option>

          <option value="fungicide">Fungicide</option>

          <option value="tillage">Tillage</option>

          <option value="weeding">Weeding</option>

          <option value="observation">Observation</option>

          <option value="incident">Incident</option>

          <option value="other">Other</option>
        </select>

        <label>Date & time</label>

        <input
          className="form-input"
          type="datetime-local"
          value={occurredAt}
          onChange={(event) => setOccurredAt(event.target.value)}
        />

        {activityType === "irrigation" && (
          <>
            <label>Duration in minutes</label>

            <input
              className="form-input"
              type="number"
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
            />

            <label>Water source</label>

            <input
              className="form-input"
              value={source}
              onChange={(event) => setSource(event.target.value)}
              placeholder="Tube well"
            />
          </>
        )}

        {inputActivity && (
          <>
            <label>Product</label>

            <input
              className="form-input"
              value={product}
              onChange={(event) => setProduct(event.target.value)}
              placeholder="Urea"
            />

            <label>Quantity / dose</label>

            <input
              className="form-input"
              type="number"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
            />

            <label>Unit</label>

            <input
              className="form-input"
              value={unit}
              onChange={(event) => setUnit(event.target.value)}
              placeholder="kg_per_acre"
            />
          </>
        )}

        <label>Notes</label>

        <textarea
          className="form-input"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />

        {error && <div className="login-error">{error}</div>}

        <div className="dialog-actions">
          <button className="secondary-action" onClick={onClose}>
            Cancel
          </button>

          <button className="primary-action" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save activity"}
          </button>
        </div>
      </div>
    </div>
  );
}

function HarvestDialog({
  field,
  cropCycle,
  onClose,
  onSaved,
}: {
  field: Field;

  cropCycle: CropCycle;

  onClose: () => void;

  onSaved: () => Promise<void>;
}) {
  const [harvestedAt, setHarvestedAt] = useState(currentDateTime());

  const [yieldKg, setYieldKg] = useState("");

  const [harvestedArea, setHarvestedArea] = useState(
    field.area_acres.toFixed(2),
  );

  const [moisture, setMoisture] = useState("");

  const [quality, setQuality] = useState("");

  const [sellingPrice, setSellingPrice] = useState("");

  const [notes, setNotes] = useState("");

  const [saving, setSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const yieldNumber = Number(yieldKg);

  const areaNumber = Number(harvestedArea);

  const liveYieldPerAcre =
    yieldNumber > 0 && areaNumber > 0 ? yieldNumber / areaNumber : null;

  const liveEstimatedValue =
    yieldNumber > 0 && Number(sellingPrice) > 0
      ? yieldNumber * Number(sellingPrice)
      : null;

  async function save() {
    if (!Number.isFinite(yieldNumber) || yieldNumber <= 0) {
      setError("Enter the total harvested yield.");

      return;
    }

    if (!Number.isFinite(areaNumber) || areaNumber <= 0) {
      setError("Harvested area must be greater than zero.");

      return;
    }

    if (moisture && (Number(moisture) < 0 || Number(moisture) > 100)) {
      setError("Moisture must be between 0 and 100.");

      return;
    }

    try {
      setSaving(true);
      setError(null);

      await harvestCropCycle(cropCycle.id, {
        harvested_at: new Date(harvestedAt).toISOString(),

        yield_kg: yieldNumber,

        harvested_area_acres: areaNumber,

        moisture_percent: moisture ? Number(moisture) : null,

        quality_grade: quality.trim() || null,

        selling_price_per_kg: sellingPrice ? Number(sellingPrice) : null,

        notes: notes.trim() || null,
      });

      await onSaved();

      onClose();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Unable to record harvest.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="dialog-card harvest-dialog">
        <h2>Record harvest</h2>

        <p className="dialog-muted">
          {field.name}
          {" · "}
          {cropCycle.crop_name}

          {cropCycle.variety ? ` · ${cropCycle.variety}` : ""}
        </p>

        <label>Harvest date & time</label>

        <input
          className="form-input"
          type="datetime-local"
          value={harvestedAt}
          onChange={(event) => setHarvestedAt(event.target.value)}
        />

        <div className="harvest-form-grid">
          <div>
            <label>Total yield</label>

            <div className="input-with-unit">
              <input
                className="form-input"
                type="number"
                min="0"
                step="0.01"
                value={yieldKg}
                onChange={(event) => setYieldKg(event.target.value)}
                placeholder="3200"
              />

              <span>kg</span>
            </div>
          </div>

          <div>
            <label>Harvested area</label>

            <div className="input-with-unit">
              <input
                className="form-input"
                type="number"
                min="0"
                step="0.01"
                value={harvestedArea}
                onChange={(event) => setHarvestedArea(event.target.value)}
              />

              <span>acres</span>
            </div>
          </div>
        </div>

        {liveYieldPerAcre != null && (
          <div className="yield-preview">
            <span>Yield per acre</span>

            <strong>
              {liveYieldPerAcre.toFixed(0)}
              {" kg/ac"}
            </strong>
          </div>
        )}

        <label>Grain / produce moisture</label>

        <div className="input-with-unit">
          <input
            className="form-input"
            type="number"
            min="0"
            max="100"
            step="0.1"
            value={moisture}
            onChange={(event) => setMoisture(event.target.value)}
            placeholder="18"
          />

          <span>%</span>
        </div>

        <label>Quality / grade</label>

        <input
          className="form-input"
          value={quality}
          onChange={(event) => setQuality(event.target.value)}
          placeholder="Grade A / FAQ / Premium"
        />

        <label>Selling price</label>

        <div className="input-with-unit">
          <input
            className="form-input"
            type="number"
            min="0"
            step="0.01"
            value={sellingPrice}
            onChange={(event) => setSellingPrice(event.target.value)}
            placeholder="24"
          />

          <span>₹/kg</span>
        </div>

        {liveEstimatedValue != null && (
          <div className="harvest-value-preview">
            <span>Estimated crop value</span>

            <strong>
              ₹
              {liveEstimatedValue.toLocaleString("en-IN", {
                maximumFractionDigits: 0,
              })}
            </strong>
          </div>
        )}

        <label>Harvest notes</label>

        <textarea
          className="form-input"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder={"Crop quality, lodging, losses, disease damage, etc."}
        />

        {error && <div className="login-error">{error}</div>}

        <div className="harvest-warning">
          Recording harvest will complete this crop cycle.
        </div>

        <div className="dialog-actions">
          <button
            className="secondary-action"
            disabled={saving}
            onClick={onClose}
          >
            Cancel
          </button>

          <button
            className="harvest-confirm-button"
            disabled={saving}
            onClick={save}
          >
            {saving ? "Recording..." : "Complete harvest"}
          </button>
        </div>
      </div>
    </div>
  );
}
