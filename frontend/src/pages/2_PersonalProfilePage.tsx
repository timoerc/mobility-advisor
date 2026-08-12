import type { PersonalProfile } from "../types";
import { INPUT } from "../ui";

type PersonalProfilePageProps = {
  profile: PersonalProfile;
  onChange: (profile: PersonalProfile) => void;
};

const inputClass = INPUT;
const labelClass = "flex flex-col gap-1";
const labelTextClass = "font-semibold text-sm text-gray-700";

export function PersonalProfilePage({
  profile,
  onChange,
}: PersonalProfilePageProps) {
  const set = <K extends keyof PersonalProfile>(key: K, value: PersonalProfile[K]) =>
    onChange({ ...profile, [key]: value });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold leading-tight mb-2">
          Tell us about yourself
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          This helps the advisor tailor recommendations to your lifestyle.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <label className={labelClass}>
          <span className={labelTextClass}>Full name</span>
          <input
            type="text"
            value={profile.full_name}
            onChange={(e) => set("full_name", e.target.value)}
            placeholder="e.g. Maja Hoffmann"
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          <span className={labelTextClass}>Age</span>
          <input
            type="number"
            min="0"
            max="120"
            value={profile.age ?? ""}
            onChange={(e) =>
              set("age", e.target.value ? Number(e.target.value) : null)
            }
            placeholder="e.g. 32"
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          <span className={labelTextClass}>Employment status</span>
          <select
            value={profile.employment_status}
            onChange={(e) =>
              set(
                "employment_status",
                e.target.value as PersonalProfile["employment_status"]
              )
            }
            className={inputClass}
          >
            <option value="employed">Employed</option>
            <option value="self-employed">Self-employed</option>
            <option value="student">Student</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label className={labelClass}>
          <span className={labelTextClass}>
            Profession{" "}
            <span className="font-normal text-gray-400">(optional)</span>
          </span>
          <input
            type="text"
            value={profile.profession}
            onChange={(e) => set("profession", e.target.value)}
            placeholder="e.g. Product Manager"
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          <span className={labelTextClass}>
            Household{" "}
            <span className="font-normal text-gray-400">(optional)</span>
          </span>
          <select
            value={profile.household_context}
            onChange={(e) =>
              set(
                "household_context",
                e.target.value as PersonalProfile["household_context"]
              )
            }
            className={inputClass}
          >
            <option value="">— select —</option>
            <option value="single">Single</option>
            <option value="partner">With partner</option>
            <option value="family">Family</option>
          </select>
        </label>
      </div>
    </div>
  );
}
