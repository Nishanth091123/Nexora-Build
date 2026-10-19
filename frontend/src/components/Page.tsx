import type { ReactNode } from "react";
import { useOutletContext } from "react-router-dom";
import { PageHeader } from "./Layout";

export default function Page({ title, subtitle, actions, children }: {
  title: string; subtitle: string; actions?: ReactNode; children: ReactNode;
}) {
  const { openMenu } = useOutletContext<{ openMenu: () => void }>();
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} onMenu={openMenu} actions={actions} />
      <main className="space-y-4 p-4 lg:p-6">{children}</main>
    </>
  );
}
