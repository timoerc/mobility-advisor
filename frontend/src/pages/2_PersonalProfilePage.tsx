import { useT } from "../i18n";
import type { PersonalProfile } from "../types";

type PersonalProfilePageProps = {
  profile: PersonalProfile;
  onChange: (profile: PersonalProfile) => void;
};

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:border-brand-red focus:ring-2 focus:ring-red-100 bg-white";
const labelClass = "flex flex-col gap-1";
const labelTextClass = "font-semibold text-sm text-gray-700";

export function PersonalProfilePage({
  profile,
  onChange,
}: PersonalProfilePageProps) {
  const t = useT();
  const set = <K extends keyof PersonalProfile>(key: K, value: PersonalProfile[K]) =>
    onChange({ ...profile, [key]: value });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold leading-tight mb-2">
          {t("onboarding.personalProfile.heading")}
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          {t("onboarding.personalProfile.subheading")}
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <label className={labelClass}>
          <span className={labelTextClass}>{t("onboarding.personalProfile.fullName")}</span>
          <input
            type="text"
            value={profile.full_name}
            onChange={(e) => set("full_name", e.target.value)}
            placeholder={t("onboarding.personalProfile.fullName.placeholder")}
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          <span className={labelTextClass}>{t("onboarding.personalProfile.age")}</span>
          <input
            type="number"
            min="0"
            max="120"
            value={profile.age ?? ""}
            onChange={(e) =>
              set("age", e.target.value ? Number(e.target.value) : null)
            }
            placeholder={t("onboarding.personalProfile.age.placeholder")}
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          <span className={labelTextClass}>{t("onboarding.personalProfile.employmentStatus")}</span>
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
            {/* option value= stays the raw English data value stored in profile data — only
                the displayed text is localized. See CarProfilePage for the same pattern. */}
            <option value="employed">{t("onboarding.personalProfile.employmentStatus.employed")}</option>
            <option value="self-employed">{t("onboarding.personalProfile.employmentStatus.selfEmployed")}</option>
            <option value="student">{t("onboarding.personalProfile.employmentStatus.student")}</option>
            <option value="other">{t("onboarding.personalProfile.employmentStatus.other")}</option>
          </select>
        </label>

        <label className={labelClass}>
          <span className={labelTextClass}>
            {t("onboarding.personalProfile.profession")}{" "}
            <span className="font-normal text-gray-400">{t("onboarding.personalProfile.optional")}</span>
          </span>
          <input
            type="text"
            value={profile.profession}
            onChange={(e) => set("profession", e.target.value)}
            placeholder={t("onboarding.personalProfile.profession.placeholder")}
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          <span className={labelTextClass}>
            {t("onboarding.personalProfile.household")}{" "}
            <span className="font-normal text-gray-400">{t("onboarding.personalProfile.optional")}</span>
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
            <option value="">{t("common.selectPlaceholder")}</option>
            <option value="single">{t("onboarding.personalProfile.household.single")}</option>
            <option value="partner">{t("onboarding.personalProfile.household.partner")}</option>
            <option value="family">{t("onboarding.personalProfile.household.family")}</option>
          </select>
        </label>
      </div>
    </div>
  );
}
