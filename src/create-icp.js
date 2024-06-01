function CreateICP() {
  return (
    <div className="d-flex justify-content-center">
      <div id="create-icp" className="d-flex flex-column mt-5 pb-5">
        <div
          id="industry"
          className="create-icp-filter container d-flex flex-column mt-4"
        >
          <label for="industry" class="form-label">
            Industry
          </label>
          <select class="form-select-sm">
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
          <label for="region" class="form-label">
            Region
          </label>
          <select class="form-select-sm">
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
          <label for="company-headcount" class="form-label">
            Company Headcount
          </label>
          <select class="form-select-sm">
            <option selected>N/A</option>
            <option value="AMER">1-10</option>
            <option value="EMEA">10-50</option>
            <option value="APAC">50-100</option>
          </select>
        </div>
        <div
          id="department-headcount"
          className="create-icp-filter container d-flex flex-column mt-4"
        >
          <label for="department-headcount" class="form-label">
            Department Headcount
          </label>
          <select class="form-select-sm">
            <option selected>N/A</option>
            <option value="AMER">1-5</option>
            <option value="EMEA">1-10</option>
            <option value="APAC">1-20</option>
            <option value="APAC">1-30</option>
            <option value="APAC">1-40</option>
          </select>
        </div>
      </div>
    </div>
  );
}

export default CreateICP;
