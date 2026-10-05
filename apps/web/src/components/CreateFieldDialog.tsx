import {
  useState,
} from "react";

import type {
  PolygonGeometry,
} from "../types/api";


type Props = {

  boundary:
    PolygonGeometry;

  onClose:
    () => void;

  onCreate:
    (
      name: string,
    ) => Promise<void>;

};


export default function CreateFieldDialog({
  onClose,
  onCreate,
}: Props) {

  const [
    name,
    setName,
  ] =
    useState("");


  const [
    saving,
    setSaving,
  ] =
    useState(false);


  async function submit() {

    if (!name.trim()) {
      return;
    }


    try {

      setSaving(true);

      await onCreate(
        name.trim(),
      );

      onClose();

    } finally {

      setSaving(false);

    }

  }


  return (
    <div className="modal-backdrop">

      <div className="dialog-card">

        <h2>
          Save field
        </h2>


        <p className="dialog-muted">

          Boundary has been drawn
          successfully.

        </p>


        <label>
          Field name
        </label>


        <input
          className="form-input"

          autoFocus

          value={name}

          onChange={(
            event,
          ) =>
            setName(
              event
                .target
                .value,
            )
          }

          placeholder="Tubewell field"
        />


        <div className="dialog-actions">

          <button
            className="secondary-action"

            onClick={
              onClose
            }
          >
            Cancel
          </button>


          <button
            className="primary-action"

            disabled={
              saving
            }

            onClick={
              submit
            }
          >

            {saving
              ? "Saving..."
              : "Save field"}

          </button>

        </div>

      </div>

    </div>
  );
}
