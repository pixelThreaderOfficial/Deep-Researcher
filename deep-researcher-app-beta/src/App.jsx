import { Routes, Route, Navigate } from "react-router-dom";
import { AIInput } from "./components/widgets";
import ChatLayout from "./components/widgets/ChatLayout";
import Chat from "./pages/Chat";
import SettingsPage from "./pages/base/Settings";
import Files from "./pages/base/_manager/Files";
import FileView from "./pages/base/_manager/File";
import Researches from "./pages/base/_manager/Researches";
import Research from "./pages/base/_manager/Research";
import { AllModels, LLMDetail, ManageModels } from "./pages/settings";
import { Toaster } from "@/components/ui/sonner";

// Main App component
const App = () => {
  return (
    <>
      <Routes>
        {/* Standalone routes */}
        <Route path="/" element={<AIInput />} />
        <Route path="/chat/:id" element={<Chat />} />
        <Route path="/chat" element={<Navigate to="/" replace />} />

        {/* Routes with sidebar and header layout */}
        <Route path="/app" element={<ChatLayout />}>
          <Route path="files" element={<Files />} />
          <Route path="files/:category" element={<FileView />} />
          <Route path="researches" element={<Researches />} />
          <Route path="research/:slug" element={<Research />} />
          <Route path="settings" element={<SettingsPage />}>
            <Route path="models" element={<AllModels />}>
              <Route path="manage" element={<ManageModels />} />
              <Route path=":model_name" element={<LLMDetail />} />
            </Route>
          </Route>
        </Route>
      </Routes>
      <Toaster />
    </>
  )
};

export default App;
