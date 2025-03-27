import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "./Dashboard.module.css";

const Dashboard = () => {
	const navigate = useNavigate();
	const [searchQuery, setSearchQuery] = useState("");
	const [typeFilter, setTypeFilter] = useState("");
	const [locationFilter, setLocationFilter] = useState("");
	const [experienceFilter, setExperienceFilter] = useState("");

	// CompanyXYZ job openings data
	const [jobOpenings, setJobOpenings] = useState([
		{
			id: 1001,
			title: "Senior Business Development Manager",
			company: "CompanyXYZ",
			location: "San Francisco, CA (Remote)",
			type: "Full-time",
			experience: "5+ years",
			postedDate: "2023-09-01",
			skills: [
				"Sales Strategy",
				"Client Acquisition",
				"Market Research",
				"Negotiation",
			],
			salary: "$120,000 - $150,000",
			description:
				"We are looking for an experienced Business Development Manager with expertise in client acquisition to join our growing team at CompanyXYZ...",
		},
		{
			id: 1002,
			title: "Strategic Partnerships Manager",
			company: "CompanyXYZ",
			location: "New York, NY",
			type: "Full-time",
			experience: "3+ years",
			postedDate: "2023-09-05",
			skills: [
				"Partnership Development",
				"Contract Negotiation",
				"Relationship Management",
				"Business Strategy",
			],
			salary: "$130,000 - $160,000",
			description:
				"Join our business team at CompanyXYZ to develop strategic partnerships and drive mutual growth with key stakeholders...",
		},
		{
			id: 1003,
			title: "Market Research Analyst",
			company: "CompanyXYZ",
			location: "Boston, MA (Hybrid)",
			type: "Full-time",
			experience: "2+ years",
			postedDate: "2023-09-10",
			skills: [
				"Market Analysis",
				"Competitive Research",
				"Data Visualization",
				"Industry Trends",
			],
			salary: "$90,000 - $120,000",
			description:
				"Conduct comprehensive market research to identify opportunities and provide strategic insights for our business development team at CompanyXYZ...",
		},
		{
			id: 1004,
			title: "Business Development Representative Intern",
			company: "CompanyXYZ",
			location: "Remote",
			type: "Internship",
			experience: "0-1 year",
			postedDate: "2023-09-12",
			skills: [
				"Lead Generation",
				"CRM Systems",
				"Sales Prospecting",
				"Communication",
			],
			salary: "$30/hour",
			description:
				"Exciting internship opportunity to work with our business development team on client acquisition and relationship building at CompanyXYZ...",
		},
		{
			id: 1005,
			title: "Account Manager",
			company: "CompanyXYZ",
			location: "Seattle, WA",
			type: "Contract",
			experience: "3+ years",
			postedDate: "2023-09-08",
			skills: [
				"Account Management",
				"Client Retention",
				"Upselling",
				"Relationship Building",
			],
			salary: "$110,000 - $140,000",
			description:
				"Help us maintain and grow relationships with existing clients while identifying upselling opportunities at CompanyXYZ...",
		},
	]);

	// Check authentication when component mounts
	useEffect(() => {
		const isLoggedIn = localStorage.getItem("candidateLoggedIn") === "true";
		if (!isLoggedIn) {
			navigate("/login");
		}
	}, [navigate]);

	// Filter jobs based on search and filters
	const filteredJobs = jobOpenings.filter((job) => {
		const matchesSearch =
			searchQuery === "" ||
			job.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
			job.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
			job.skills.some((skill) =>
				skill.toLowerCase().includes(searchQuery.toLowerCase())
			);

		const matchesType = typeFilter === "" || job.type === typeFilter;
		const matchesLocation =
			locationFilter === "" || job.location.includes(locationFilter);
		const matchesExperience =
			experienceFilter === "" ||
			job.experience.includes(experienceFilter);

		return (
			matchesSearch && matchesType && matchesLocation && matchesExperience
		);
	});

	return (
		<div className={styles.dashboardContainer}>
			<div className={styles.content}>
				<div className={styles.welcomeSection}>
					<h2>Join Our Team at CompanyXYZ</h2>
					<p>
						Discover exciting career opportunities and be part of
						our mission to innovate and transform the industry.
					</p>
				</div>

				<div className={styles.jobFilters}>
					<div className={styles.searchBar}>
						<input
							type="text"
							placeholder="Search for positions, skills, or departments"
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
						/>
						<button className={styles.searchButton}>
							<i className="fa fa-search"></i>
						</button>
					</div>

					<div className={styles.filterOptions}>
						<select
							value={typeFilter}
							onChange={(e) => setTypeFilter(e.target.value)}
							className={styles.filterSelect}
						>
							<option value="">All Job Types</option>
							<option value="Full-time">Full-time</option>
							<option value="Part-time">Part-time</option>
							<option value="Contract">Contract</option>
							<option value="Internship">Internship</option>
						</select>

						<select
							value={locationFilter}
							onChange={(e) => setLocationFilter(e.target.value)}
							className={styles.filterSelect}
						>
							<option value="">All Locations</option>
							<option value="Remote">Remote</option>
							<option value="Hybrid">Hybrid</option>
							<option value="San Francisco">San Francisco</option>
							<option value="New York">New York</option>
							<option value="Boston">Boston</option>
							<option value="Seattle">Seattle</option>
						</select>

						<select
							value={experienceFilter}
							onChange={(e) =>
								setExperienceFilter(e.target.value)
							}
							className={styles.filterSelect}
						>
							<option value="">All Experience Levels</option>
							<option value="0-1">Entry Level (0-1 year)</option>
							<option value="2+">Mid Level (2+ years)</option>
							<option value="5+">Senior Level (5+ years)</option>
						</select>
					</div>
				</div>

				<div className={styles.jobListings}>
					<h3>Current Openings ({filteredJobs.length})</h3>

					{filteredJobs.length === 0 ? (
						<div className={styles.noJobsFound}>
							<p>
								No positions match your current filters. Try
								adjusting your search criteria.
							</p>
						</div>
					) : (
						filteredJobs.map((job) => (
							<div key={job.id} className={styles.jobCard}>
								<div className={styles.jobMain}>
									<div className={styles.jobTitleSection}>
										<h4 className={styles.jobTitle}>
											{job.title}
										</h4>
										<div className={styles.companyInfo}>
											<span
												className={styles.jobLocation}
											>
												<i className="fa fa-map-marker"></i>{" "}
												{job.location}
											</span>
										</div>
									</div>

									<div className={styles.jobAttributes}>
										<span className={styles.jobType}>
											{job.type}
										</span>
										<span className={styles.jobExperience}>
											<i className="fa fa-briefcase"></i>{" "}
											{job.experience}
										</span>
										<span className={styles.jobSalary}>
											<i className="fa fa-money"></i>{" "}
											{job.salary}
										</span>
										<span className={styles.jobDate}>
											<i className="fa fa-calendar"></i>{" "}
											Posted:{" "}
											{new Date(
												job.postedDate
											).toLocaleDateString()}
										</span>
									</div>

									<div className={styles.jobDescription}>
										<p>{job.description}</p>
									</div>

									<div className={styles.jobSkills}>
										{job.skills.map((skill, index) => (
											<span
												key={index}
												className={styles.skillTag}
											>
												{skill}
											</span>
										))}
									</div>
								</div>

								<div className={styles.jobActions}>
									<Link
										to={`/job/${job.id}`}
										className={styles.viewButton}
									>
										View Details
									</Link>
									<Link
										to={`/job/${job.id}?apply=true`}
										className={styles.applyButton}
									>
										Apply Now
									</Link>
								</div>
							</div>
						))
					)}
				</div>
			</div>
		</div>
	);
};

export default Dashboard;
