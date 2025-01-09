import { Outlet } from "react-router";

// Base Accounts View that routes to Accounts table
// and Leads in Account table.
const AccountsView = () => {
  return (
    <div className="w-11/12 mx-auto">
      <Outlet />
    </div>
  );
};

export default AccountsView;
