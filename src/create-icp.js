function CreateICP() {
  return (
    <div className="d-flex justify-content-center">
      <div id="create-icp" className="d-flex flex-column mt-5 pb-5">
        <div
          id="industry"
          className="create-icp-filter container d-flex flex-column mt-4"
        >
          <label for="industry" className="form-label">
            Industry
          </label>
          <select className="form-select-sm">
            <option selected>N/A</option>
            <option value="Saas">SaaS</option>
            <option value="Real Estate">Real Estate</option>
            <option value="Banking">Banking</option>
            <option value="Media">Media & Entertainment</option>
          </select>
        </div>
        <div
          id="region"
          className="create-icp-filter container d-flex flex-column mt-4"
        >
          <label for="region" className="form-label">
            Region
          </label>
          <select className="form-select-sm">
            <option selected>N/A</option>
            <option value="AMER">AMER</option>
            <option value="EMEA">EMEA</option>
            <option value="APAC">APAC</option>
          </select>
        </div>
        <div
          id="company-headcount"
          className="create-icp-filter container d-flex flex-column mt-4"
        >
          <label for="company-headcount" className="form-label">
            Company Headcount
          </label>
          <select className="form-select-sm">
            <option selected>N/A</option>
            <option value="1-10">1-10</option>
            <option value="10-50">10-50</option>
            <option value="50-100">50-100</option>
          </select>
        </div>
        <div
          id="function-headcount"
          className="create-icp-filter container d-flex flex-column mt-4"
        >
          <label for="function-headcount" className="form-label">
            Function Headcount
          </label>
          <select className="form-select-sm">
            <option selected>Function Name</option>
            <option value="Marketing">Marketing</option>
            <option value="Sales">Sales</option>
            <option value="Engineering">Engineering</option>
            <option value="IT">IT</option>
            <option value="HR">HR</option>
          </select>
          <select className="form-select-sm mt-2">
            <option selected>N/A</option>
            <option value="1-5">1-5</option>
            <option value="1-10">1-10</option>
            <option value="1-20">1-20</option>
            <option value="1-30">1-30</option>
            <option value="1-40">1-40</option>
          </select>
        </div>
      </div>
    </div>
  );
}

export default CreateICP;
