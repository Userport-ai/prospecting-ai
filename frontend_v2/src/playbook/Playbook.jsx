import { Outlet } from "react-router";

function Playbook() {
  return (
    <div className="w-full flex items-center justify-center min-h-screen my-10">
      <Outlet />
    </div>
  );
}

export default Playbook;
