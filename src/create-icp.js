import { useState } from "react";
import CreateAccountFilters from "./create-account-filters";

function CreateICP() {
  const [currentStep, setCurrentStep] = useState(1);
  const [icpInfo, setIcpInfo] = useState({
    accountFilters: {},
    personaFilters: [],
  });

  function handleAccountFiltersUpdate(updatedAccountFilters) {
    setIcpInfo({ ...icpInfo, accountFilters: updatedAccountFilters });
  }

  function handlePersonaFiltersUpdate(updatedPersonaFilters) {
    setIcpInfo({ ...icpInfo, personaFilters: updatedPersonaFilters });
  }

  function handleNextStepClick() {
    // setCurrentStep(currentStep + 1);
    console.log("current step bro: ", currentStep);
  }

  function handlePrevStepClick() {
    setCurrentStep(currentStep - 1);
  }

  switch (currentStep) {
    case 1:
      return (
        <>
          <CreateAccountFilters
            onAccountFiltersUpdate={handleAccountFiltersUpdate}
            onNextStepClick={handleNextStepClick}
          />
          <CreateAccountFilters
            onAccountFiltersUpdate={handleAccountFiltersUpdate}
            onNextStepClick={handleNextStepClick}
          />
          <CreateAccountFilters
            onAccountFiltersUpdate={handleAccountFiltersUpdate}
            onNextStepClick={handleNextStepClick}
          />
        </>
      );
    default:
      return null;
  }
}

export default CreateICP;
