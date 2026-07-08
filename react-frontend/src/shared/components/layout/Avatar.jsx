import React from 'react';
// Make sure you have an avatar image at this path.
// You can use a PNG or JPG file.
import avatarImage from 'assets/avatar.jpeg'; 
import './Avatar.css';

export default function Avatar() {
    return (
        <div className="avatar-container-static">
            <img 
                src={avatarImage} 
                alt="Interview Avatar" 
                className="avatar-image-static"
            />
        </div>
    );
}