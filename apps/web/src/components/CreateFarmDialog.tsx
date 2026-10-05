import {
  useState,
} from "react";


type Props = {

  onClose:
    () => void;

  onCreate:
    (
      name: string,
      location:
        string | null,
    ) => Promise<void>;

};


export default function CreateFarmDialog({
  onClose,
  onCreate,
}: Props) {

  const [
    name,
    setName,
  ] =
    useState("");


  const [
    location,
    setLocation,
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

        location.trim()
          || null,
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
          Add farm
        </h2>


        <label>
          Farm name
        </label>

        <input
          className="form-input"

          value={name}

          onChange={(
            event,
          ) =>
            setName(
              event.target.value,
            )
          }

          placeholder="Karnal Farm"
        />


        <label>
          Location
        </label>

        <input
          className="form-input"

          value={location}

          onChange={(
            event,
          ) =>
            setLocation(
              event.target.value,
            )
          }

          placeholder="Karnal, Haryana"
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
              ? "Creating..."
              : "Create farm"}

          </button>

        </div>

      </div>

    </div>
  );
}
