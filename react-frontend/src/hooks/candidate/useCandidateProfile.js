import { useCallback, useEffect, useState } from "react";
import {
  getProfile,
  updateProfile,
  uploadCV,
  uploadPhoto,
  viewPhoto,
  updateCvDetails,
} from "../../services/api";

export default function useCandidateProfile(toast) {
  const [bio, setBio] = useState({
    name: "",
    email: "",
    phone: "",
    location: "",
    title: "",
    about: "",
    skills: [],
  });
  const [profilePhotoUrl, setProfilePhotoUrl] = useState(null);
  const [cvPath, setCvPath] = useState(null);
  const [cvDetails, setCvDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploadingCV, setUploadingCV] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const profile = await getProfile();
      setBio({
        name: profile.name || "",
        email: profile.email || "",
        phone: profile.phone || "",
        location: profile.location || "",
        title: profile.title || "",
        about: profile.about || "",
        skills: profile.skills || [],
      });
      if (profile.cv_path) setCvPath(profile.cv_path);
      if (profile.cv_details) setCvDetails(profile.cv_details);
      if (profile.profile_photo) {
        try {
          const blob = await viewPhoto();
          setProfilePhotoUrl(URL.createObjectURL(blob));
        } catch {}
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = useCallback(async () => {
    try {
      await updateProfile(bio);
      toast?.("Profile updated successfully!", "success");
      return true;
    } catch (e) {
      toast?.("Failed to update profile", "error");
      return false;
    }
  }, [bio, toast]);

  const uploadCvFile = useCallback(
    async (file) => {
      if (!file) return false;
      setUploadingCV(true);
      try {
        const res = await uploadCV(file);
        setCvPath(res.cv_path);
        toast?.("CV uploaded successfully!", "success");
        return true;
      } catch (e) {
        toast?.("Failed to upload CV", "error");
        return false;
      } finally {
        setUploadingCV(false);
      }
    },
    [toast]
  );

  const uploadProfilePhoto = useCallback(
    async (file) => {
      if (!file) return false;
      setUploadingPhoto(true);
      try {
        await uploadPhoto(file);
        // reload photo blob
        try {
          const blob = await viewPhoto();
          setProfilePhotoUrl(URL.createObjectURL(blob));
        } catch {}
        toast?.("Photo uploaded successfully!", "success");
        return true;
      } catch (e) {
        toast?.("Failed to upload photo", "error");
        return false;
      } finally {
        setUploadingPhoto(false);
      }
    },
    [toast]
  );

  const saveCvDetails = useCallback(
    async (cvDetailsData) => {
      try {
        await updateCvDetails(cvDetailsData);
        setCvDetails(cvDetailsData);
        toast?.("CV details saved successfully!", "success");
        return true;
      } catch (e) {
        console.error("Failed to save CV details:", e);
        toast?.("Failed to save CV details", "error");
        return false;
      }
    },
    [toast]
  );

  return {
    bio,
    setBio,
    profilePhotoUrl,
    cvPath,
    cvDetails,
    setCvDetails,
    loading,
    uploadingCV,
    uploadingPhoto,
    load,
    save,
    uploadCvFile,
    uploadProfilePhoto,
    saveCvDetails,
  };
}
