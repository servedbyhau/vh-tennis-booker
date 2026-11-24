import type { RouteObject } from "react-router";
import { App } from "./App";
import { Redirect } from "./components/Redirect";
import { ErrorPage } from "./pages/ErrorPage";
import { GuidePage } from "./pages/GuidePage";
import { HomePage } from "./pages/HomePage";
import { CustomersTab } from "./pages/management/CustomersTab";
import { HistoryTab } from "./pages/management/HistoryTab";
import { MachinesTab } from "./pages/management/MachinesTab";
import { MoneyTab } from "./pages/management/MoneyTab";
import { OverviewTab } from "./pages/management/OverviewTab";
import { QuotaTab } from "./pages/management/QuotaTab";
import { RequestsTab } from "./pages/management/RequestsTab";
import { StatsTab } from "./pages/management/StatsTab";
import { TicketsTab } from "./pages/management/TicketsTab";
import { ManagementPage } from "./pages/ManagementPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OLD_PATHS, paths } from "./paths";

/** Every screen under the app's layout; shared by the browser router and the tests. */
export const routes: RouteObject[] = [
  {
    path: paths.overview,
    element: <App />,
    errorElement: <ErrorPage />,
    children: [
      { index: true, element: <HomePage /> },
      {
        path: paths.management,
        element: <ManagementPage />,
        children: [
          { index: true, element: <OverviewTab /> },
          { path: paths.machines, element: <MachinesTab /> },
          { path: paths.customers, element: <CustomersTab /> },
          { path: paths.tickets, element: <TicketsTab /> },
          { path: paths.quota, element: <QuotaTab /> },
          { path: paths.money, element: <MoneyTab /> },
          { path: paths.requests, element: <RequestsTab /> },
          { path: paths.history, element: <HistoryTab /> },
          { path: paths.stats, element: <StatsTab /> },
        ],
      },
      { path: paths.guide, element: <GuidePage /> },
      ...OLD_PATHS.map(([path, to]) => ({ path, element: <Redirect to={to} /> })),
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
