import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "./Dashboard.module.css";

const Dashboard = () => {
	const navigate = useNavigate();
	const [searchQuery, setSearchQuery] = useState("");
	const [typeFilter, setTypeFilter] = useState("");
	const [locationFilter, setLocationFilter] = useState("");
	const [experienceFilter, setExperienceFilter] = useState("");

	// Sample job openings data
	const [jobOpenings, setJobOpenings] = useState([
		{
			id: 1001,
			title: "Senior Frontend Developer",
			company: "Tech Innovations Inc.",
			location: "San Francisco, CA (Remote)",
			type: "Full-time",
			experience: "5+ years",
			postedDate: "2023-09-01",
			skills: ["React", "TypeScript", "GraphQL", "Redux"],
			salary: "$120,000 - $150,000",
			description:
				"We are looking for an experienced Frontend Developer with expertise in React to join our growing team...",
		},
		{
			id: 1002,
			title: "Full Stack Engineer",
			company: "Global Systems",
			location: "New York, NY",
			type: "Full-time",
			experience: "3+ years",
			postedDate: "2023-09-05",
			skills: ["Node.js", "React", "MongoDB", "AWS"],
			salary: "$130,000 - $160,000",
			description:
				"Join our engineering team to build innovative solutions for enterprise clients...",
		},
		{
			id: 1003,
			title: "UX/UI Designer",
			company: "DataViz Solutions",
			location: "Boston, MA (Hybrid)",
			type: "Full-time",
			experience: "2+ years",
			postedDate: "2023-09-10",
			skills: ["Figma", "Adobe XD", "UI/UX", "Prototyping"],
			salary: "$90,000 - $120,000",
			description:
				"Create beautiful and intuitive user interfaces for our data visualization products...",
		},
		{
			id: 1004,
			title: "Machine Learning Engineer Intern",
			company: "AI Horizons",
			location: "Remote",
			type: "Internship",
			experience: "0-1 year",
			postedDate: "2023-09-12",
			skills: ["Python", "TensorFlow", "PyTorch", "Data Analysis"],
			salary: "$30/hour",
			description:
				"Exciting internship opportunity to work with our AI research team on cutting-edge projects...",
		},
		{
			id: 1005,
			title: "DevOps Engineer",
			company: "CloudScale Technologies",
			location: "Seattle, WA",
			type: "Contract",
			experience: "3+ years",
			postedDate: "2023-09-08",
			skills: ["Kubernetes", "Docker", "CI/CD", "Terraform"],
			salary: "$110,000 - $140,000",
			description:
				"Help us scale and maintain our cloud infrastructure and deployment pipelines...",
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
			job.company.toLowerCase().includes(searchQuery.toLowerCase()) ||
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
					<h2>Find Your Dream Job</h2>
					<p>
						Discover and apply to exciting job opportunities that
						match your skills and interests.
					</p>
				</div>

				<div className={styles.jobFilters}>
					<div className={styles.searchBar}>
						<input
							type="text"
							placeholder="Search for jobs, skills, or companies"
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
								No jobs match your current filters. Try
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
											<span className={styles.jobCompany}>
												{job.company}
											</span>
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
