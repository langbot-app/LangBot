#!/usr/bin/env node

import { argv, exit } from "node:process";
import { parseGlobalArgs, usage } from "./cli.ts";
import { commandCaseList, commandCaseNew, commandCaseShow } from "./commands/case.ts";
import { commandEnvDoctor, commandEnvShow } from "./commands/env.ts";
import { commandFixtureCheck, commandFixtureList } from "./commands/fixture.ts";
import { commandIndex, commandList, commandNewRef, commandNewSkill } from "./commands/skill.ts";
import { commandLogGuard, commandLogScan, commandLogWatch } from "./commands/log.ts";
import { commandSuiteList, commandSuiteNew, commandSuitePlan, commandSuiteReport, commandSuiteRun, commandSuiteShow, commandSuiteStart } from "./commands/suite.ts";
import { commandTestPlan, commandTestRecommend, commandTestReport, commandTestResult, commandTestRun, commandTestStart } from "./commands/test.ts";
import { commandTroubleAdd, commandTroubleList, commandTroubleSearch, commandTroubleShow } from "./commands/trouble.ts";
import { commandValidate } from "./commands/validate.ts";

async function main(): Promise<number> {
  const ctx = parseGlobalArgs(argv.slice(2));
  const command = ctx.args[0];
  if (!command) usage();

  if (command === "list") return commandList(ctx);
  if (command === "validate") return commandValidate(ctx.root);
  if (command === "index") return commandIndex(ctx);
  if (command === "new-skill") return commandNewSkill(ctx);
  if (command === "new-ref") return commandNewRef(ctx);

  if (command === "env") {
    const sub = ctx.args[1];
    if (sub === "show") return commandEnvShow(ctx);
    if (sub === "doctor") return await commandEnvDoctor(ctx);
  }

  if (command === "fixture") {
    const sub = ctx.args[1];
    if (sub === "list") return commandFixtureList(ctx);
    if (sub === "check") return commandFixtureCheck(ctx);
  }

  if (command === "log") {
    const sub = ctx.args[1];
    if (sub === "scan") return commandLogScan(ctx);
    if (sub === "watch") return await commandLogWatch(ctx);
    if (sub === "guard") return commandLogGuard(ctx);
  }

  if (command === "case") {
    const sub = ctx.args[1];
    if (sub === "new") return commandCaseNew(ctx);
    if (sub === "list") return commandCaseList(ctx);
    if (sub === "show") return commandCaseShow(ctx);
  }

  if (command === "suite") {
    const sub = ctx.args[1];
    if (sub === "new") return commandSuiteNew(ctx);
    if (sub === "list") return commandSuiteList(ctx);
    if (sub === "show") return commandSuiteShow(ctx);
    if (sub === "plan") return commandSuitePlan(ctx);
    if (sub === "start") return commandSuiteStart(ctx);
    if (sub === "run") return commandSuiteRun(ctx);
    if (sub === "report") return commandSuiteReport(ctx);
  }

  if (command === "test") {
    const sub = ctx.args[1];
    if (sub === "plan") return commandTestPlan(ctx);
    if (sub === "recommend") return commandTestRecommend(ctx);
    if (sub === "start") return commandTestStart(ctx);
    if (sub === "run") return commandTestRun(ctx);
    if (sub === "report") return commandTestReport(ctx);
    if (sub === "result") return commandTestResult(ctx);
  }

  if (command === "trouble") {
    const sub = ctx.args[1];
    if (sub === "list") return commandTroubleList(ctx);
    if (sub === "show") return commandTroubleShow(ctx);
    if (sub === "search") return commandTroubleSearch(ctx);
    if (sub === "add") return commandTroubleAdd(ctx);
  }

  usage();
}

exit(await main());
