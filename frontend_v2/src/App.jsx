import { Button } from "./components/ui/button";

function App() {
  return (
    <div className="flex flex-row justify-center items-center min-h-screen bg-slate-100 font-inter">
      <div className="flex flex-col gap-2">
        <div>
          <p className="text-violet-600 font-semibold text-center">
            Hello Userport
          </p>
        </div>
        <Button>ShadCN Button</Button>
      </div>
    </div>
  );
}

export default App;
