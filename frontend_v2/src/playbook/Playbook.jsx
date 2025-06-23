import { Outlet } from "react-router";

function Playbook() {
  return (
    <div className="w-full flex justify-center my-10">
      <Outlet />
    </div>
  );
}

export default Playbook;
