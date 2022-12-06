# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC 
# MAGIC <div style="text-align: center; line-height: 0; padding-top: 9px;">
# MAGIC   <img src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png" alt="Databricks Learning" style="width: 600px">
# MAGIC </div>

# COMMAND ----------

# MAGIC %md # Classification: Logistic Regression
# MAGIC 
# MAGIC Up until this point, we have only examined regression use cases. Now let's take a look at how to handle classification.
# MAGIC 
# MAGIC For this lab, we will use the same Airbnb dataset, but instead of predicting price, we will predict if host is a <a href="https://www.airbnb.com/superhost" target="_blank">superhost</a> or not in San Francisco.
# MAGIC 
# MAGIC ## ![Spark Logo Tiny](https://files.training.databricks.com/images/105/logo_spark_tiny.png) In this lesson you:<br>
# MAGIC  - Build a Logistic Regression model
# MAGIC  - Use various metrics to evaluate model performance

# COMMAND ----------

# MAGIC %run "../Includes/Classroom-Setup"

# COMMAND ----------

file_path = f"{datasets_dir}/airbnb/sf-listings/sf-listings-2019-03-06-clean.delta/"
airbnb_df = spark.read.format("delta").load(file_path)

# COMMAND ----------

# MAGIC %md ## Baseline Model
# MAGIC 
# MAGIC Before we build any Machine Learning models, we want to build a baseline model to compare to. We are going to start by predicting if a host is a <a href="https://www.airbnb.com/superhost" target="_blank">superhost</a>. 
# MAGIC 
# MAGIC For our baseline model, we are going to predict no on is a superhost and evaluate our accuracy. We will examine other metrics later as we build more complex models.
# MAGIC 
# MAGIC 0. Convert our **`host_is_superhost`** column (t/f) into 1/0 and call the resulting column **`label`**. DROP the **`host_is_superhost`** afterwards.
# MAGIC 0. Add a column to the resulting DataFrame called **`prediction`** which contains the literal value **`0.0`**. We will make a constant prediction that no one is a superhost.
# MAGIC 
# MAGIC After we finish these two steps, then we can evaluate the "model" accuracy. 
# MAGIC 
# MAGIC Some helpful functions:
# MAGIC * <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.sql.functions.when.html#pyspark.sql.functions.when" target="_blank">when()</a>
# MAGIC * <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.sql.DataFrame.withColumn.html?highlight=withcolumn#pyspark.sql.DataFrame.withColumn" target="_blank">withColumn()</a>
# MAGIC * <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.sql.functions.lit.html?highlight=lit#pyspark.sql.functions.lit" target="_blank">lit()</a>

# COMMAND ----------

# ANSWER

from pyspark.sql.functions import when, col, lit

label_df = airbnb_df.select(when(col("host_is_superhost") == "t", 1.0).otherwise(0.0).alias("label"), "*").drop("host_is_superhost")

pred_df = label_df.withColumn("prediction", lit(0.0))

# COMMAND ----------

# MAGIC %md ## Evaluate model
# MAGIC 
# MAGIC For right now, let's use accuracy as our metric. This is available from <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.evaluation.MulticlassClassificationEvaluator.html?highlight=multiclassclassificationevaluator#pyspark.ml.evaluation.MulticlassClassificationEvaluator" target="_blank">MulticlassClassificationEvaluator</a>.

# COMMAND ----------

from pyspark.ml.evaluation import MulticlassClassificationEvaluator

mc_evaluator = MulticlassClassificationEvaluator(metricName="accuracy")
print(f"The accuracy is {100*mc_evaluator.evaluate(pred_df):.2f}%")

# COMMAND ----------

# MAGIC %md ## Train-Test Split
# MAGIC 
# MAGIC Alright! Now we have built a baseline model. The next step is to split our data into a train-test split.

# COMMAND ----------

train_df, test_df = label_df.randomSplit([.8, .2], seed=42)
print(train_df.cache().count())

# COMMAND ----------

# MAGIC %md ## Visualize
# MAGIC 
# MAGIC Let's look at the relationship between **`review_scores_rating`** and **`label`** in our training dataset.

# COMMAND ----------

display(train_df.select("review_scores_rating", "label"))

# COMMAND ----------

# MAGIC %md ## Logistic Regression
# MAGIC 
# MAGIC Now build a <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.classification.LogisticRegression.html?highlight=logisticregression#pyspark.ml.classification.LogisticRegression" target="_blank">logistic regression model</a> using all of the features (HINT: use RFormula). Put the pre-processing step and the Logistic Regression Model into a Pipeline.

# COMMAND ----------

# ANSWER
from pyspark.ml import Pipeline
from pyspark.ml.feature import RFormula
from pyspark.ml.classification import LogisticRegression

r_formula = RFormula(formula="label ~ .", 
                    featuresCol="features", 
                    labelCol="label", 
                    handleInvalid="skip") # Look at handleInvalid

lr = LogisticRegression(labelCol="label", featuresCol="features")
pipeline = Pipeline(stages=[r_formula, lr])
pipeline_model = pipeline.fit(train_df)
pred_df = pipeline_model.transform(test_df)

# COMMAND ----------

# MAGIC %md ## Evaluate
# MAGIC 
# MAGIC What is AUROC useful for? Try adding additional evaluation metrics, like Area Under PR Curve.

# COMMAND ----------

# ANSWER
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator

mc_evaluator = MulticlassClassificationEvaluator(metricName="accuracy")
print(f"The accuracy is {100*mc_evaluator.evaluate(pred_df):.2f}%")

bc_evaluator = BinaryClassificationEvaluator(metricName="areaUnderROC")
print(f"The area under the ROC curve: {bc_evaluator.evaluate(pred_df):.2f}")

bc_evaluator.setMetricName("areaUnderPR")
print(f"The area under the PR curve: {bc_evaluator.evaluate(pred_df):.2f}")

# COMMAND ----------

# MAGIC %md ## Add Hyperparameter Tuning
# MAGIC 
# MAGIC Try changing the hyperparameters of the logistic regression model using the cross-validator. By how much can you improve your metrics? 

# COMMAND ----------

# ANSWER
from pyspark.ml.tuning import ParamGridBuilder
from pyspark.ml.tuning import CrossValidator

param_grid = (ParamGridBuilder()
            .addGrid(lr.regParam, [0.1, 0.2])
            .addGrid(lr.elasticNetParam, [0.0, 0.5, 1.0])
            .build())

cv = CrossValidator(estimator=lr, evaluator=mc_evaluator, estimatorParamMaps=param_grid,
                    numFolds=3, parallelism=4, seed=42)

pipeline = Pipeline(stages=[r_formula, cv])

pipeline_model = pipeline.fit(train_df)

pred_df = pipeline_model.transform(test_df)

# COMMAND ----------

# MAGIC %md ## Evaluate again

# COMMAND ----------

mc_evaluator = MulticlassClassificationEvaluator(metricName="accuracy")
print(f"The accuracy is {100*mc_evaluator.evaluate(pred_df):.2f}%")

bc_evaluator = BinaryClassificationEvaluator(metricName="areaUnderROC")
print(f"The area under the ROC curve: {bc_evaluator.evaluate(pred_df):.2f}")

# COMMAND ----------

# MAGIC %md ## Super Bonus
# MAGIC 
# MAGIC Try using MLflow to track your experiments!

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC &copy; 2022 Databricks, Inc. All rights reserved.<br/>
# MAGIC Apache, Apache Spark, Spark and the Spark logo are trademarks of the <a href="https://www.apache.org/">Apache Software Foundation</a>.<br/>
# MAGIC <br/>
# MAGIC <a href="https://databricks.com/privacy-policy">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use">Terms of Use</a> | <a href="https://help.databricks.com/">Support</a>
