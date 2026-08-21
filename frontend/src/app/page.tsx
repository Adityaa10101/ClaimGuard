"use client";

import React, { useState, useEffect } from "react";
import { ShieldCheck, Upload, Play, CheckCircle, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function Home() {
  const [narrative, setNarrative] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [presets, setPresets] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    fetch("http://localhost:8000/api/presets")
      .then((res) => res.json())
      .then((data) => setPresets(data))
      .catch((err) => console.error("Failed to load presets", err));
  }, []);

  const loadPreset = (type: "clean" | "flagged") => {
    if (presets && presets[type]) {
      setNarrative(presets[type].narrative);
      // For presets, we need to create a File object from the string so it can be uploaded
      const file = new File([presets[type].metrics_csv], "metrics.csv", { type: "text/csv" });
      setCsvFile(file);
      setResult(null);
    }
  };

  const handleAudit = async () => {
    if (!narrative || !csvFile) {
      alert("Please provide both narrative text and a CSV metrics file.");
      return;
    }

    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append("narrative", narrative);
    formData.append("metrics_file", csvFile);

    try {
      const response = await fetch("http://localhost:8000/api/audit", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Audit request failed");
      }

      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error(error);
      alert("Error executing audit pipeline.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-8 md:p-12 lg:p-24 max-w-7xl mx-auto font-sans">
      
      {/* Header */}
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel p-8 rounded-3xl mb-12 flex flex-col md:flex-row items-center gap-6"
      >
        <div className="bg-slate-800/50 p-4 rounded-2xl">
          <ShieldCheck className="w-16 h-16 text-sky-400" />
        </div>
        <div>
          <h1 className="text-4xl md:text-5xl font-extrabold text-gradient mb-2 tracking-tight">
            ClaimGuard Audit Engine
          </h1>
          <p className="text-slate-400 text-lg max-w-3xl leading-relaxed">
            Deterministic ESG & BRSR verification engine. Combines LLM structured claim extraction 
            with pure Python/Pandas mathematical verification to eliminate AI hallucinated math.
          </p>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
        {/* Input Section */}
        <motion.div 
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-panel rounded-3xl p-8 flex flex-col"
        >
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold text-slate-200">1. Narrative PR Text</h2>
            <div className="flex gap-2">
              <button 
                onClick={() => loadPreset("clean")}
                className="text-xs bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 px-3 py-1.5 rounded-full font-medium transition"
              >
                Preset: Clean
              </button>
              <button 
                onClick={() => loadPreset("flagged")}
                className="text-xs bg-rose-500/20 text-rose-400 hover:bg-rose-500/30 px-3 py-1.5 rounded-full font-medium transition"
              >
                Preset: Flagged
              </button>
            </div>
          </div>
          <textarea
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            className="w-full bg-slate-900/50 border border-slate-700 rounded-2xl p-4 text-slate-300 h-64 focus:ring-2 focus:ring-sky-500 focus:outline-none transition resize-none mb-6"
            placeholder="Paste your sustainability PR claim or BRSR narrative text here..."
          />

          <h2 className="text-xl font-bold text-slate-200 mb-4">2. Ground-Truth Metrics</h2>
          <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-slate-700 border-dashed rounded-2xl cursor-pointer bg-slate-900/30 hover:bg-slate-800/50 transition">
            <div className="flex flex-col items-center justify-center pt-5 pb-6">
              <Upload className="w-8 h-8 text-slate-400 mb-2" />
              <p className="text-sm text-slate-400">
                <span className="font-semibold text-sky-400">Click to upload</span> or drag and drop
              </p>
              <p className="text-xs text-slate-500 mt-1">metrics.csv file</p>
            </div>
            <input 
              type="file" 
              className="hidden" 
              accept=".csv"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  setCsvFile(e.target.files[0]);
                }
              }} 
            />
          </label>
          {csvFile && (
            <div className="mt-3 text-sm text-emerald-400 flex items-center gap-2 bg-emerald-900/20 p-2 rounded-lg border border-emerald-500/30">
              <CheckCircle className="w-4 h-4" /> {csvFile.name} loaded
            </div>
          )}
        </motion.div>

        {/* Results Section */}
        <motion.div 
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-panel rounded-3xl p-8 flex flex-col"
        >
          <div className="flex-1 flex flex-col justify-center">
            
            {!result && !loading && (
              <div className="text-center text-slate-500 flex flex-col items-center">
                <ShieldCheck className="w-20 h-20 mb-4 opacity-20" />
                <p>Run the audit pipeline to see verification results here.</p>
              </div>
            )}

            {loading && (
              <div className="text-center flex flex-col items-center justify-center">
                <div className="w-12 h-12 border-4 border-sky-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                <p className="text-sky-400 font-medium animate-pulse">Extracting claim & mathematically verifying...</p>
              </div>
            )}

            {result && !loading && (
              <AnimatePresence>
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex flex-col h-full"
                >
                  <h2 className="text-xl font-bold text-slate-200 mb-6">3. Audit Findings</h2>
                  
                  <div className="flex items-start gap-4 mb-8 p-6 rounded-2xl bg-slate-900/60 border border-slate-700">
                    {result.audit_result.status === "PASS" ? (
                      <div className="shrink-0 flex items-center justify-center bg-emerald-500 text-white font-bold text-xl px-6 py-3 rounded-xl glow-pass shadow-lg">
                        ✅ PASS
                      </div>
                    ) : (
                      <div className="shrink-0 flex items-center justify-center bg-rose-500 text-white font-bold text-xl px-6 py-3 rounded-xl glow-flagged shadow-lg">
                        🚨 FLAGGED
                      </div>
                    )}
                    <p className={`text-sm md:text-base ${result.audit_result.status === "PASS" ? 'text-emerald-300' : 'text-rose-300'}`}>
                      {result.audit_result.discrepancy_reason}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-700/50">
                      <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Claimed Reduction</p>
                      <p className="text-2xl font-bold text-white">{result.audit_result.claimed_percentage.toFixed(2)}%</p>
                    </div>
                    <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-700/50">
                      <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Calculated Delta</p>
                      <p className="text-2xl font-bold text-white">{result.audit_result.calculated_delta.toFixed(2)}%</p>
                    </div>
                    <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-700/50">
                      <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Math Variance</p>
                      <p className="text-2xl font-bold text-white">{result.audit_result.variance.toFixed(2)}%</p>
                    </div>
                    <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-700/50">
                      <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Ground Truth</p>
                      <p className="text-xl font-bold text-white">
                        {result.audit_result.baseline_value?.toLocaleString()} → {result.audit_result.target_value?.toLocaleString()}
                      </p>
                    </div>
                  </div>

                  {/* Tabs */}
                  <div className="flex gap-4 border-b border-slate-700 mb-4">
                    <button 
                      onClick={() => setActiveTab("overview")}
                      className={`pb-2 text-sm font-medium transition-colors ${activeTab === 'overview' ? 'text-sky-400 border-b-2 border-sky-400' : 'text-slate-400 hover:text-slate-300'}`}
                    >
                      Math Breakdown
                    </button>
                    <button 
                      onClick={() => setActiveTab("json")}
                      className={`pb-2 text-sm font-medium transition-colors ${activeTab === 'json' ? 'text-sky-400 border-b-2 border-sky-400' : 'text-slate-400 hover:text-slate-300'}`}
                    >
                      Extracted JSON
                    </button>
                  </div>

                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-sm font-mono text-slate-300 overflow-auto flex-1 max-h-[200px]">
                    {activeTab === 'json' ? (
                      <pre>{JSON.stringify(result.extracted_claim, null, 2)}</pre>
                    ) : (
                      <div className="space-y-2">
                        <p><span className="text-sky-400">Metric Row:</span> {result.audit_result.matched_metric}</p>
                        <p><span className="text-sky-400">Baseline ({result.audit_result.baseline_year}):</span> {result.audit_result.baseline_value?.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
                        <p><span className="text-sky-400">Target ({result.audit_result.target_year}):</span> {result.audit_result.target_value?.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
                        <p><span className="text-emerald-400">Formula:</span> ((Baseline - Target) / Baseline) * 100</p>
                        <p><span className="text-emerald-400">Calculation:</span> (({result.audit_result.baseline_value?.toLocaleString(undefined, {minimumFractionDigits: 2})} - {result.audit_result.target_value?.toLocaleString(undefined, {minimumFractionDigits: 2})}) / {result.audit_result.baseline_value?.toLocaleString(undefined, {minimumFractionDigits: 2})}) * 100 = {result.audit_result.calculated_delta}%</p>
                      </div>
                    )}
                  </div>
                </motion.div>
              </AnimatePresence>
            )}

          </div>
        </motion.div>
      </div>

      {/* Action Button */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="flex justify-center"
      >
        <button 
          onClick={handleAudit}
          disabled={loading}
          className="group relative flex items-center justify-center gap-3 bg-sky-500 hover:bg-sky-400 text-white font-bold text-xl px-12 py-5 rounded-full shadow-[0_0_40px_rgba(56,189,248,0.3)] hover:shadow-[0_0_60px_rgba(56,189,248,0.5)] transition-all disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden"
        >
          <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out" />
          <Play className="w-6 h-6 fill-current relative z-10" />
          <span className="relative z-10">Run Deterministic Audit Pipeline</span>
        </button>
      </motion.div>

    </div>
  );
}
