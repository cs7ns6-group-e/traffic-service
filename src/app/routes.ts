import { lazy } from "react";
import { createBrowserRouter } from "react-router";

const Login = lazy(() => import("./pages/Login"));
const DriverDashboard = lazy(() => import("./pages/DriverDashboard"));
const BookJourney = lazy(() => import("./pages/BookJourney"));
const JourneyDetail = lazy(() => import("./pages/JourneyDetail"));
const TrafficAuthorityDashboard = lazy(() => import("./pages/TrafficAuthorityDashboard"));
const AdminDashboard = lazy(() => import("./pages/AdminDashboard"));
const Notifications = lazy(() => import("./pages/Notifications"));
const Settings = lazy(() => import("./pages/Settings"));
const DashboardLayout = lazy(() => import("./layouts/DashboardLayout"));

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Login,
  },
  {
    path: "/login",
    Component: Login,
  },
  {
    path: "/driver",
    Component: DashboardLayout,
    children: [
      { index: true, Component: DriverDashboard },
      { path: "book-journey", Component: BookJourney },
      { path: "journey/:id", Component: JourneyDetail },
      { path: "notifications", Component: Notifications },
      { path: "settings", Component: Settings },
    ],
  },
  {
    path: "/authority",
    Component: DashboardLayout,
    children: [
      { index: true, Component: TrafficAuthorityDashboard },
      { path: "notifications", Component: Notifications },
      { path: "settings", Component: Settings },
    ],
  },
  {
    path: "/admin",
    Component: DashboardLayout,
    children: [
      { index: true, Component: AdminDashboard },
      { path: "notifications", Component: Notifications },
      { path: "settings", Component: Settings },
    ],
  },
]);
