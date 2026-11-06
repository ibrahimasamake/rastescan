import { useState } from "react";
import { ApiError, officerApi } from "../api";
import { ErrorBox, Skeleton, Toast, useAsync, useToast } from "../components/States";
import { useI18n } from "../i18n";
import { usePortal } from "../portal";
import { OfficerShell } from "./Shell";

export default function Team() {
  return <OfficerShell><TeamBody /></OfficerShell>;
}

function TeamBody() {
  const { t, date } = useI18n();
  const { officer } = usePortal();
  const list = useAsync(() => officerApi.officers(), []);
  const [form, setForm] = useState({ email: "", name: "", role: "officer", password: "" });
  const [err, setErr] = useState<string | null>(null);
  const [toast, show] = useToast();
  if (officer.role !== "admin") return <p>{t("officer.notAllowed")}</p>;

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      await officerApi.createOfficer(form);
      setForm({ email: "", name: "", role: "officer", password: "" });
      show(t("officer.done"));
      list.reload();
    } catch (x) {
      setErr(x instanceof ApiError ? x.message : t("common.error"));
    }
  };
  const update = async (id: number, body: { active?: boolean; password?: string }) => {
    try {
      await officerApi.updateOfficer(id, body);
      show(t("officer.done"));
      list.reload();
    } catch (x) {
      show(x instanceof ApiError ? x.message : t("common.error"));
    }
  };
  return (
    <>
      <p className="muted">{t("officer.teamLead")}</p>
      <p><a className="btn outline small" href={officerApi.adminExportUrl()}>{t("officer.export")}</a></p>
      {list.loading && !list.data && <Skeleton h={200} />}
      {!!list.error && !list.data && <ErrorBox error={list.error} retry={list.reload} />}
      {list.data && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>{t("officer.name")}</th><th>{t("officer.email")}</th><th>{t("officer.role")}</th><th>{t("officer.active")}</th><th /></tr></thead>
            <tbody>
              {list.data.map((o) => (
                <tr key={o.id}>
                  <td>{o.name}</td>
                  <td>{o.email}</td>
                  <td>{o.role === "admin" ? t("officer.roleAdmin") : t("officer.roleOfficer")}</td>
                  <td title={date(o.created_at)}>{o.active ? t("common.yes") : t("common.no")}</td>
                  <td className="btn-row">
                    <button className="btn ghost small" onClick={() => update(o.id, { active: !o.active })}>{o.active ? t("officer.deactivate") : t("officer.activate")}</button>
                    <button className="btn ghost small" onClick={() => {
                      const p = window.prompt(t("officer.newPassword"));
                      if (p) update(o.id, { password: p });
                    }}>{t("officer.newPassword")}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form className="card pad filters" onSubmit={add}>
        <div className="field"><label htmlFor="o-name">{t("officer.name")}</label><input id="o-name" className="input" required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div className="field"><label htmlFor="o-email">{t("officer.email")}</label><input id="o-email" className="input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <div className="field"><label htmlFor="o-role">{t("officer.role")}</label>
          <select id="o-role" className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            <option value="officer">{t("officer.roleOfficer")}</option><option value="admin">{t("officer.roleAdmin")}</option>
          </select></div>
        <div className="field"><label htmlFor="o-pw">{t("officer.password")}</label><input id="o-pw" className="input" type="password" autoComplete="new-password" required minLength={10} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
        <button className="btn small">{t("officer.add")}</button>
        {err && <p className="error-text" role="alert">{err}</p>}
      </form>
      <Toast msg={toast} />
    </>
  );
}
