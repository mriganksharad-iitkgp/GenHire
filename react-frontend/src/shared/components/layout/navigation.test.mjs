import test from "node:test";
import assert from "node:assert/strict";
import { recruiterTab, navigationItems, navigationActive, legacyCandidateApplications } from "./navigation.js";

test("recruiter sections follow valid queries and default when query is removed", () => {
  for (const tab of ["overview", "jobs", "candidates", "profile"]) assert.equal(recruiterTab(`?tab=${tab}`), tab);
  for (const search of ["", "?tab=unknown", "?tab="]) assert.equal(recruiterTab(search), "overview");
  const links = navigationItems("recruiter");
  assert.equal(links.length, 6);
  for (const link of links) {
    const url = new URL(link.to, "https://example.test");
    assert.equal(navigationActive(link, url), true);
  }
  assert.deepEqual(links.filter(link => navigationActive(link, {pathname:"/recruiter/dashboard",search:"",hash:""})).map(link=>link.id), ["overview"]);
});

test("candidate navigation keeps profile separate and marks application details active", () => {
  const links = navigationItems("candidate");
  const app = links.find(link => link.id === "applications");
  const profile = links.find(link => link.id === "profile");
  assert.equal(app.to, "/applications");
  assert.equal(profile.to, "/profile");
  assert.equal(navigationActive(app, {pathname:"/applications",search:"",hash:""}), true);
  assert.equal(navigationActive(app, {pathname:"/applications/123",search:"",hash:""}), true);
  assert.equal(navigationActive(app, {pathname:"/profile",search:"",hash:""}), false);
  assert.equal(navigationActive(profile, {pathname:"/profile",search:"",hash:"#bio"}), true);
  assert.deepEqual(navigationItems("candidate", true).map(link=>link.id), ["jobs","applications","profile"]);
});

test("old candidate applications bookmarks migrate without dropping other query parameters", () => {
  assert.equal(legacyCandidateApplications({pathname:"/profile",search:"",hash:"#applications"}), "/applications");
  assert.equal(legacyCandidateApplications({pathname:"/profile",search:"?tab=applications&source=email",hash:""}), "/applications?source=email");
  assert.equal(legacyCandidateApplications({pathname:"/profile",search:"?tab=applications",hash:"#bio"}), null);
  assert.equal(legacyCandidateApplications({pathname:"/profile",search:"",hash:""}), null);
});
