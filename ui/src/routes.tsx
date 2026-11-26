import type { RouteObject } from "react-router";
import { App } from "./App";
import { Redirect } from "./components/Redirect";
import { ErrorPage } from "./pages/ErrorPage";
import { HomePage } from "./pages/HomePage";
import { CustomersTab } from "./pages/management/CustomersTab";
import { HistoryTab } from "./pages/management/HistoryTab";
import { OverviewTab } from "./pages/management/OverviewTab";
import { QuotaTab } from "./pages/management/QuotaTab";
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
          { path: paths.customers, element: <CustomersTab /> },
          { path: paths.tickets, element: <TicketsTab /> },
          { path: paths.quota, element: <QuotaTab /> },
          { path: paths.history, element: <HistoryTab /> },
          { path: paths.stats, element: <StatsTab /> },
        ],
      },
      ...OLD_PATHS.map(([path, to]) => ({ path, element: <Redirect to={to} /> })),
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
