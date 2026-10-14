import {
  useState,
} from "react";

import {
  localDateInputValue,
} from "../lib/dates";


type Props = {
  onClose:
    () => void;

  onCreate:
    (
      name: string,
      seasonType: string | null,
      startedOn: string,
    ) => Promise<void>;
};


export default function CreateSeasonDialog({
  onClose,
  onCreate,
}: Props) {
  const [
    name,
    setName,
  ] = useState(
    `Season ${new Date().getFullYear()}`,
  );

  const [
    seasonType,
    setSeasonType,
  ] = useState("");

  const [
    startedOn,
    setStartedOn,
  ] = useState(localDateInputValue());

  const [
    saving,
    setSaving,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );


  async function submit() {
    if (!name.trim()) {
      setError(
        "Season name is required.",
      );

      return;
    }


    try {
      setSaving(true);
      setError(null);

      await onCreate(
        name.trim(),
        seasonType.trim() || null,
        startedOn,
      );

      onClose();

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create season.",
      );

    } finally {
      setSaving(false);
    }
  }


  return (
    <div className="modal-backdrop">

      <div className="dialog-card">

        <h2>
          Create season
        </h2>


        <label>
          Season name
        </label>

        <input
          className="form-input"

          value={name}

          onChange={(event) =>
            setName(
              event.target.value,
            )
          }

          placeholder="Kharif 2026"
        />


        <label>
          Season type
        </label>

        <select
          className="form-input"

          value={seasonType}

          onChange={(event) =>
            setSeasonType(
              event.target.value,
            )
          }
        >
          <option value="">
            Select type
          </option>

          <option value="Kharif">
            Kharif
          </option>

          <option value="Rabi">
            Rabi
          </option>

          <option value="Zaid">
            Zaid
          </option>

          <option value="Orchard">
            Orchard / Perennial
          </option>

          <option value="Other">
            Other
          </option>
        </select>


        <label>
          Start date
        </label>

        <input
          className="form-input"

          type="date"

          value={startedOn}

          onChange={(event) =>
            setStartedOn(
              event.target.value,
            )
          }
        />


        {error && (
          <div className="login-error">
            {error}
          </div>
        )}


        <div className="dialog-actions">

          <button
            className="secondary-action"

            onClick={onClose}

            disabled={saving}
          >
            Cancel
          </button>


          <button
            className="primary-action"

            onClick={submit}

            disabled={saving}
          >
            {saving
              ? "Creating..."
              : "Create season"}
          </button>

        </div>

      </div>

    </div>
  );
}
