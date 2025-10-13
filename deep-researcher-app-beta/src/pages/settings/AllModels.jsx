import React from 'react'
import { Outlet } from 'react-router-dom'

const AllModels = () => {
    return (
        <div>
            AllModels
            {/* Nested routes for manage and :model_name render here */}
            <Outlet />
        </div>
    )
}

export default AllModels